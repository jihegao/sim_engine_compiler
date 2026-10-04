"""Read-only source-bound replay of J09.var02 SCRPT=2 item repair."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse, populated, scale_roundtrip_lossless

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "j09-var02-scrpt2-v100-ssh-20261004-01"
RUN = HERE / "runs" / RUN_ID
PARENT = ROOT / "E04-upstream-transport-slow-v1.0.0"
PARENT_RUN = PARENT / "runs/e04-slow-v100-ssh-20260929-01"
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


def validate() -> dict:
    failures: list[str] = []
    checks = 0

    def ck(label: str, result: bool) -> None:
        nonlocal checks
        checks += 1
        if not result:
            failures.append(label)

    contract, invocation, closure = (load(HERE / "contract.json"), load(RUN / "invocation.json"), load(RUN / "closure.json"))
    ck("case and variant", contract["case_id"] == "J09" and contract["variant_id"] == "J09.var02")
    ck("frozen source", contract["scaled_input_sha256"] == sha(HERE / "scaled-input.json") == sha(RUN / "input.json"))
    ck("frozen diff", contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("parent source", contract["accepted_parent"]["input_sha256"] == sha(PARENT / "native-input.json"))
    ck("parent closure", contract["accepted_parent"]["closure_sha256"] == sha(PARENT_RUN / "closure.json"))
    ck("parent signoff", contract["accepted_parent"]["signoff_sha256"] == sha(PARENT / "cli-scope-signoff-2026-09-29.md"))
    ck("scale precedent", contract["scale_schema_precedent"]["input_sha256"] == sha(PRECEDENT / "scaled-input.json") and
       contract["scale_schema_precedent"]["closure_sha256"] == sha(PRECEDENT / "runs/j09-var06-sctrt2-v101-ssh-20261004-01/closure.json") and
       contract["scale_schema_precedent"]["evidence_index_sha256"] == sha(PRECEDENT / "evidence-index.json"))
    ck("run identity and success", invocation["run_id"] == closure["run_id"] == RUN_ID and closure["error"] is None)
    ck("session-0 ssh and queue", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("preserved GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    ck("invocation seal", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    ck("sources stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
    bound = {"input": HERE / "scaled-input.json", "exact_diff": HERE / "exact-diff.json", "contract": HERE / "contract.json",
             "parent": PARENT / "native-input.json", "parent_closure": PARENT_RUN / "closure.json",
             "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
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
        ck(f"raw file seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    steps = load(RUN / "steps.json")
    ck("native step order", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
    for step in steps:
        ck(f"step complete {step['name']}", step["status"] == "completed" and step["exit_code"] == 0)
    for step in steps[:4]:
        ck(f"GUI preserved {step['name']}", step["gui_preserved"] is True)
    checker = load(RUN / "roundtrip-validation.json")
    ck("roundtrip gate", checker["passed"] is True and checker["differences"] == [] and len(checker["populated_tables"]) == 22)
    original, exported = populated(parse(RUN / "input.json")), populated(parse(RUN / "roundtrip-raw.json"))
    for name, table in original.items():
        ck(f"lossless table {name}", exported.get(name) == table if name != "ScaleFactors" else scale_roundtrip_lossless(table, exported[name]))
    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter diagnostics", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1}) and
       not re.search(r"\((?:warning|notice) #(?!(?:108)\))", runlog))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    def event(data: str, time: str, fragment: str) -> bool:
        return sum(line.startswith(f"Time: {time} ") and fragment in line for line in data.splitlines()) == 1
    ck("same first fault", event(log,"9.8829","critical random failure added") and event(parent_log,"9.8829","critical random failure added"))
    ck("same base demand/removal", event(log,"10","Backorder added") and event(log,"10.1667","remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed"))
    for data,label in ((log,"child"),(parent_log,"parent")):
        ck(f"unchanged upstream transport {label}", event(data,"10.1667","transport task 0 starts with 1 items/systems, transport time: 2") and event(data,"12.1667","transport task 0 arrives with 1 items/systems"))
        ck(f"unchanged downstream transport {label}", event(data,"12.1667","transport task 2 starts with 1 items/systems, transport time: 2") and event(data,"14.1667","transport task 2 arrives with 1 items/systems"))
        ck(f"same physical items {label}", event(data,"12.1667","Item requiring maintenance arrives <TEACH-LRU-01,0,1>") and event(data,"12.1667","Take replacement item <TEACH-LRU-01,0,0> from stock") and event(data,"14.1667","Replacement item arrives <TEACH-LRU-01,0,0>"))
    ck("child two-hour depot direct repair", event(log,"12.1667","direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,1> starts performing, planned to last for 2 hours") and event(log,"14.1667","direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,1> completed") and event(log,"14.1667","Put back replacement item <TEACH-LRU-01,0,1> to stock"))
    ck("parent one-hour depot direct repair", event(parent_log,"12.1667","direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,1> starts performing, planned to last for 1 hours") and event(parent_log,"13.1667","direct repair subtask 2 seqno 0 within item DIRP task 1 on <TEACH-LRU-01,0,1> completed") and event(parent_log,"13.1667","Put back replacement item <TEACH-LRU-01,0,1> to stock"))
    ck("child restock shifted exactly one hour", not event(log,"13.1667","Put back replacement item <TEACH-LRU-01,0,1> to stock") and not event(parent_log,"14.1667","Put back replacement item <TEACH-LRU-01,0,1> to stock"))
    ck("same backorder and readiness", event(log,"14.1667","Backorder removed, waiting time was 4.16667") and event(log,"14.5","System ready <TEACH-AIR-01,0>") and event(parent_log,"14.1667","Backorder removed, waiting time was 4.16667") and event(parent_log,"14.5","System ready <TEACH-AIR-01,0>"))
    ck("same missions", all(event(data,"9.8829","mission aborted:") and event(data,"22","mission success:") and event(data,"34","mission success:") for data in (log,parent_log)))
    ck("one logistics and repair cycle", len(re.findall("Backorder added",log)) == len(re.findall("Backorder removed",log)) == len(re.findall("Take replacement item",log)) == len(re.findall("Put back replacement item",log)) == 1 and len(re.findall(r"transport task \d+ starts with 1 items/systems",log)) == 2)
    report, parent_report = parse(RUN / "report-raw.json"), parse(PARENT_RUN / "report-raw.json")
    ck("report byte-identical to parent", sha(RUN / "report-raw.json") == sha(PARENT_RUN / "report-raw.json"))
    ck("report tables identical", report == parent_report and [t["name"] for t in report["report"]["tables"]] == ["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"])
    summary = rows(report,"ResultSummary")
    ck("36-hour mission summary", len(summary)==1 and summary[0]["RTIUP"]==36 and abs(summary[0]["MSUF"]-2/3)<1e-6)
    for name in ("SystemResults","StockTotalResults"):
        child_rows, parent_rows = rows(report,name), rows(parent_report,name)
        ck(f"72 half-hour {name} bins", len(child_rows)==72 and all(r["STINT"]==i*.5 and r["ETINT"]==(i+1)*.5 for i,r in enumerate(child_rows)))
        for i,(child,parent) in enumerate(zip(child_rows,parent_rows)):
            ck(f"same {name} bin {i}", child==parent)
    system, stock = rows(report,"SystemResults"), rows(report,"StockTotalResults")
    ck("terminal ready/no backorder", system[-1]["NSYRY"]==system[-1]["NSYA"]==1 and stock[-1]["NBO"]==0)
    ck("one failure/repair/demand", sum(r["NFAIL"] for r in system)==sum(r["NREPT"] for r in system)==sum(r["NDF"] for r in stock)==1)
    return {"schema":"simlox-j09-var02-v100-author-native-validation/v1","case_id":"J09","variant_id":"J09.var02",
            "run_id":RUN_ID,"passed":not failures,"checks":checks,"differences":failures,
            "input_sha256":sha(RUN/"input.json"),"model_log_sha256":sha(RUN/"model.log"),
            "report_sha256":sha(RUN/"report-raw.json"),"closure_sha256":sha(RUN/"closure.json"),
            "scope":"one depot item direct-repair TAT scaled from one to two hours; aggregate report unchanged",
            "publication_state":"not_published"}


if __name__ == "__main__":
    answer=validate()
    print(json.dumps(answer,indent=2))
    raise SystemExit(0 if answer["passed"] else 1)
