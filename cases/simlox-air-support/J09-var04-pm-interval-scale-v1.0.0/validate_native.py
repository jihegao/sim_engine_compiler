"""Read-only source-bound replay of J09.var04 SCPMI=2 calendar PM."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated, scale_roundtrip_lossless

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "j09-var04-scpmi2-v100-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID
PARENT = ROOT / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs/d03-calendar-v100-ssh-20261001-02"
PRECEDENT = ROOT / "J09-var06-transport-scale-v1.0.1"
RAW = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
       "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
       "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def occupancy(start: float, end: float, bin_start: float) -> float:
    return max(0.0, min(end, bin_start + .5) - max(start, bin_start)) / .5


def validate() -> dict:
    failures: list[str] = []
    checks = 0

    def ck(label: str, result: bool) -> None:
        nonlocal checks
        checks += 1
        if not result:
            failures.append(label)

    contract, invocation, closure = load(HERE / "contract.json"), load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck("case and variant", contract["case_id"] == "J09" and contract["variant_id"] == "J09.var04")
    ck("frozen child source", contract["scaled_input_sha256"] == sha(HERE / "scaled-input.json") == sha(RUN / "input.json"))
    ck("frozen exact diff", contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("parent source", contract["accepted_parent"]["input_sha256"] == sha(PARENT / "native-input.json"))
    ck("parent closure", contract["accepted_parent"]["closure_sha256"] == sha(PARENT_RUN / "closure.json"))
    ck("parent signoff", contract["accepted_parent"]["signoff_sha256"] == sha(PARENT / "cli-scope-signoff-2026-09-30.md"))
    ck("scale schema precedent", contract["scale_schema_precedent"]["input_sha256"] == sha(PRECEDENT / "scaled-input.json") and
       contract["scale_schema_precedent"]["closure_sha256"] == sha(PRECEDENT / "runs/j09-var06-sctrt2-v101-ssh-20261004-01/closure.json") and
       contract["scale_schema_precedent"]["evidence_index_sha256"] == sha(PRECEDENT / "evidence-index.json"))
    ck("successful run identity", invocation["run_id"] == closure["run_id"] == RUN_ID and closure["error"] is None)
    ck("session-0 SSH and host queue", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    ck("source stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    bound = {"input": HERE / "scaled-input.json", "exact_diff": HERE / "exact-diff.json", "contract": HERE / "contract.json",
             "parent": PARENT / "native-input.json", "parent_closure": PARENT_RUN / "closure.json",
             "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
             "precedent_input": PRECEDENT / "scaled-input.json",
             "precedent_closure": PRECEDENT / "runs/j09-var06-sctrt2-v101-ssh-20261004-01/closure.json",
             "precedent_evidence_index": PRECEDENT / "evidence-index.json",
             "build.py": HERE / "build.py", "describe_diff.py": HERE / "describe_diff.py",
             "check_roundtrip.py": HERE / "check_roundtrip.py", "run_native_ssh.ps1": HERE / "run_native_ssh.ps1"}
    for name, path in bound.items():
        ck(f"bound source {name}", closure["source_hashes_before"].get(name) == sha(path))
    ck("raw file set", set(closure["raw"]) == RAW)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    steps = load(RUN / "steps.json")
    ck("step order", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"step completed {step['name']}", step["status"] == "completed" and step["exit_code"] == 0)
    for step in steps[:4]:
        ck(f"GUI preserved {step['name']}", step["gui_preserved"] is True)
    checker = load(RUN / "roundtrip-validation.json")
    ck("lossless roundtrip gate", checker["passed"] is True and checker["differences"] == [] and len(checker["populated_tables"]) == 19)
    original, exported = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    for name, table in original.items():
        ck(f"lossless table {name}", exported.get(name) == table if name != "ScaleFactors" else scale_roundtrip_lossless(table, exported[name]))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and
       Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1, "126": 1}) and
       not re.search(r"\((?:warning|notice) #(?!(?:108|126)\))", runlog))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    def event(data: str, time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in data.splitlines()) == 1
    starts = re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$",log,re.M)
    completions = re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$",log,re.M)
    parent_starts = re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$",parent_log,re.M)
    parent_completions = re.findall(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$",parent_log,re.M)
    ck("PM starts shifted", starts == ["48"] and parent_starts == ["24","49"])
    ck("PM completes shifted", completions == ["49"] and parent_completions == ["25","50"])
    ck("one child CAL24 PM task", event(log,"48","system PM task 0 on <TEACH-AIR-01,0> PMID: CAL24") and not re.search(r"system PM task 1 on <TEACH-AIR-01,0> started",log))
    ck("one-hour child subtask", event(log,"48","subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 1 hours") and event(log,"49","subtask 0 seqno 1 within system PM task 0 on <TEACH-AIR-01,0> completed"))
    ck("child ready span", event(log,"48","nbr ready decreased at unit") and event(log,"49","nbr ready increased at unit") and event(log,"49","System ready <TEACH-AIR-01,0>"))
    ck("no PM resource demand", event(log,"48","requests resources: no resources needed"))
    for data,label in ((log,"child"),(parent_log,"parent")):
        for hour in ("10","22","34"):
            ck(f"{label} mission success {hour}", sum(line.startswith(f"Time: {hour} <BASIC-MISSION,TEACH-UNIT") and "mission success:" in line for line in data.splitlines()) == 1)
        ck(f"{label} three missions", len(re.findall(r"<BASIC-MISSION,TEACH-UNIT.*mission success:",data)) == 3 and "mission aborted:" not in data)

    report, parent_report = parse(RUN / "report-raw.json"), parse(PARENT_RUN / "report-raw.json")
    summary, parent_summary = rows(report,"ResultSummary"), rows(parent_report,"ResultSummary")
    ck("same mission summary", summary == parent_summary and len(summary) == 1 and summary[0]["RTIUP"] == 60 and summary[0]["MSUF"] == 1)
    system, parent_system = rows(report,"SystemResults"), rows(parent_report,"SystemResults")
    stock, parent_stock = rows(report,"StockTotalResults"), rows(parent_report,"StockTotalResults")
    ck("120 aligned half-hour bins", all(len(table)==120 and all(r["STINT"]==i*.5 and r["ETINT"]==(i+1)*.5 for i,r in enumerate(table)) for table in (system,parent_system,stock,parent_stock)))
    for i,(child,parent) in enumerate(zip(stock,parent_stock)):
        ck(f"same stock bin {i}", child == parent)
    ck("one child PM start/completion", sum(r["NPMS"] for r in system) == sum(r["NPMT"] for r in system) == 1)
    ck("one child PM aircraft-hour", abs(sum(r["NSYPM"] for r in system)*.5 - 1) < 2e-5)
    ck("parent two PM aircraft-hours", abs(sum(r["NSYPM"] for r in parent_system)*.5 - 2) < 2e-5)
    ck("child terminal ready", system[-1]["NSYRY"] == system[-1]["NSYA"] == 1 and system[-1]["NSYPM"] == 0)
    changed = {"NSYRY","NSYUA","NSYA","NSYPM","NPMS","NPMT","SYDT","NSYDT"}
    for i,(child,parent) in enumerate(zip(system,parent_system)):
        start=i*.5
        p_occ = occupancy(24,25,start) + occupancy(49,50,start)
        c_occ = occupancy(48,49,start)
        ck(f"PM occupancy bin {i}", abs(child["NSYPM"]-c_occ)<3e-5 and abs(parent["NSYPM"]-p_occ)<3e-5)
        ck(f"PM unavailable bin {i}", abs(child["NSYUA"]-parent["NSYUA"]-(c_occ-p_occ))<3e-5)
        ck(f"ready bin {i}", abs(child["NSYRY"]-parent["NSYRY"]+(c_occ-p_occ))<3e-5)
        ck(f"available bin {i}", abs(child["NSYA"]-parent["NSYA"]+(c_occ-p_occ))<3e-5)
        ck(f"PM flags bin {i}", child["NPMS"] == int(i==96) and child["NPMT"] == int(i==98) and parent["NPMS"] == int(i in (48,98)) and parent["NPMT"] == int(i in (50,100)))
        ck(f"downtime start flags bin {i}", child["NSYDT"] == int(i==96) and parent["NSYDT"] == int(i in (48,98)) and child["SYDT"] == (1 if i==96 else None) and parent["SYDT"] == (1 if i in (48,98) else None))
        for key in set(child)-changed:
            ck(f"unchanged system {key} bin {i}", child[key]==parent[key])
    return {"schema":"simlox-j09-var04-v100-author-native-validation/v1","case_id":"J09","variant_id":"J09.var04",
            "run_id":RUN_ID,"passed":not failures,"checks":checks,"differences":failures,
            "input_sha256":sha(RUN/"input.json"),"model_log_sha256":sha(RUN/"model.log"),
            "report_sha256":sha(RUN/"report-raw.json"),"closure_sha256":sha(RUN/"closure.json"),
            "scope":"one CALHOURS 24h PM interval scaled to first PM at48h; one hour task; 60h window",
            "publication_state":"not_published"}


if __name__ == "__main__":
    result=validate()
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["passed"] else 1)
