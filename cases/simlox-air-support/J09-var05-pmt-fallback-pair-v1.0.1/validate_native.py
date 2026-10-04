"""Author replay of sealed matched task-free SCPMT arms."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_control_roundtrip import parse, populated, scale_roundtrip_lossless

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "D03-calendar-pm-v1.0.0"
DIAGNOSTIC = ROOT / "J09-var05-pm-tat-scale-v1.0.0"
RUNS = {
    "control": HERE / "runs/j09-var05-pmt-control-v101-ssh-20261004-01",
    "scaled": HERE / "runs/j09-var05-pmt-scaled-v101-ssh-20261004-01",
}
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
    return [dict(zip(columns, row)) for inst in table["instances"] for row in inst["rows"]]


def occupancy(start: float, end: float, t: float) -> float:
    return max(0.0, min(end, t + .5) - max(start, t)) / .5


def validate() -> dict:
    checks = 0
    failures: list[str] = []

    def ck(label: str, ok: bool) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    ck("case variant", (contract["case_id"], contract["variant_id"]) == ("J09", "J09.var05"))
    ck("parent input", sha(PARENT / "native-input.json") == contract["accepted_parent"]["input_sha256"])
    ck("parent closure", sha(PARENT / "runs/d03-calendar-v100-ssh-20261001-02/closure.json") == contract["accepted_parent"]["closure_sha256"])
    ck("parent signoff", sha(PARENT / "cli-scope-signoff-2026-09-30.md") == contract["accepted_parent"]["signoff_sha256"])
    ck("excluded diagnostic closure", sha(DIAGNOSTIC / "runs/j09-var05-scpmt2-v100-ssh-20261004-01/closure.json") == contract["excluded_diagnostic"]["closure_sha256"])
    ck("exact diff", sha(HERE / "exact-diff.json") == contract["exact_diff_sha256"])

    event_times: dict[str, tuple[list[float], list[float], list[float]]] = {}
    reports: dict[str, dict] = {}
    for arm, run in RUNS.items():
        invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
        input_sha = contract[f"{arm}_input_sha256"]
        ck(f"{arm} input", sha(HERE / f"{arm}-input.json") == sha(run / "input.json") == input_sha)
        ck(f"{arm} run identity", invocation["run_id"] == closure["run_id"] == run.name and closure["error"] is None)
        ck(f"{arm} SSH queue", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        ck(f"{arm} GUI identity", invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
        ck(f"{arm} invocation seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
        ck(f"{arm} source stable", closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"])
        bound = {"input": HERE / f"{arm}-input.json", "other_arm": HERE / f"{'scaled' if arm == 'control' else 'control'}-input.json",
                 "contract": HERE / "contract.json", "exact_diff": HERE / "exact-diff.json",
                 "parent": PARENT / "native-input.json",
                 "parent_closure": PARENT / "runs/d03-calendar-v100-ssh-20261001-02/closure.json",
                 "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
                 "excluded_closure": DIAGNOSTIC / "runs/j09-var05-scpmt2-v100-ssh-20261004-01/closure.json",
                 "build.py": HERE / "build.py", "describe_diff.py": HERE / "describe_diff.py",
                 f"check_{arm}_roundtrip.py": HERE / f"check_{arm}_roundtrip.py",
                 f"run_{arm}_ssh.ps1": HERE / f"run_{arm}_ssh.ps1"}
        for name, path in bound.items():
            ck(f"{arm} source {name}", closure["source_hashes_before"].get(name) == sha(path))
        ck(f"{arm} raw set", set(closure["raw"]) == RAW)
        for name, seal in closure["raw"].items():
            path = run / name
            ck(f"{arm} raw seal {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        steps = load(run / "steps.json")
        ck(f"{arm} steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"])
        for step in steps:
            ck(f"{arm} step {step['name']}", step["status"] == "completed" and step["exit_code"] == 0 and (step.get("gui_preserved") is True if step["name"] != "check_import_export" else True))
        roundtrip = load(run / "roundtrip-validation.json")
        ck(f"{arm} roundtrip", roundtrip["passed"] is True and roundtrip["differences"] == [] and len(roundtrip["populated_tables"]) == 19)
        before, after = populated(parse(run / "input.json")), populated(parse(run / "roundtrip-raw.json"))
        for name, table in before.items():
            ck(f"{arm} table {name}", after.get(name) == table if name != "ScaleFactors" else scale_roundtrip_lossless(table, after[name]))
        runlog = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{arm} converter", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog and
           Counter(re.findall(r"\(warning #(\d+)\)", runlog)) == Counter({"108": 1, "126": 1}) and
           not re.search(r"\((?:warning|notice) #(?!(?:108|126)\))", runlog))
        log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
        def times(pattern: str) -> list[float]:
            return [float(v) for v in re.findall(pattern, log, re.M)]
        starts = times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> started$")
        ends = times(r"^Time: ([\d.]+)  system PM task \d+ on <TEACH-AIR-01,0> completed$")
        planned = times(r"^Time: [\d.]+  subtask \d+ seqno 0 within system PM task \d+ on <TEACH-AIR-01,0> starts performing, planned to last for ([\d.]+) hours$")
        event_times[arm] = starts, ends, planned
        expected = ([24.0, 49.0], [25.0, 50.0], [1.0, 1.0]) if arm == "control" else ([24.0, 52.0], [28.0, 56.0], [4.0, 4.0])
        ck(f"{arm} PM event durations", (starts, ends, planned) == expected)
        ck(f"{arm} PM identity", len(re.findall(r"PMID: CAL24$", log, re.M)) == 2)
        ck(f"{arm} PM resource-free", log.count("requests resources: no resources needed") == 2)
        for t in (10, 22, 34):
            ck(f"{arm} mission success {t}", len(re.findall(rf"^Time: {t} <BASIC-MISSION,TEACH-UNIT.*mission success:", log, re.M)) == 1)
        ck(f"{arm} no mission abort", "mission aborted:" not in log and "mission cancelled:" not in log)
        reports[arm] = parse(run / "report-raw.json")

    ck("direct PM duration contrast", event_times["control"] != event_times["scaled"])
    control, scaled = reports["control"], reports["scaled"]
    cs, ss = rows(control, "SystemResults"), rows(scaled, "SystemResults")
    ct, st = rows(control, "StockTotalResults"), rows(scaled, "StockTotalResults")
    parent_report = PARENT / "runs/d03-calendar-v100-ssh-20261001-02/report-raw.json"
    ck("control report equals accepted D03", sha(RUNS["control"] / "report-raw.json") == sha(parent_report))
    ck("same mission summary", rows(control, "ResultSummary") == rows(scaled, "ResultSummary") and len(rows(control, "ResultSummary")) == 1)
    ck("120 aligned report bins", all(len(table) == 120 and all(row["STINT"] == i * .5 and row["ETINT"] == (i + 1) * .5 for i, row in enumerate(table)) for table in (cs, ss, ct, st)))
    changed = {"NSYRY", "NSYUA", "NSYA", "NSYPM", "NPMT", "NPMS", "SYDT", "NSYDT"}
    for i, (c, s, stock_c, stock_s) in enumerate(zip(cs, ss, ct, st)):
        t = i * .5
        c_occ = occupancy(24, 25, t) + occupancy(49, 50, t)
        s_occ = occupancy(24, 28, t) + occupancy(52, 56, t)
        ck(f"stock bin {i}", stock_c == stock_s)
        ck(f"control PM bin {i}", abs(c["NSYPM"] - c_occ) < 3e-5)
        ck(f"scaled PM bin {i}", abs(s["NSYPM"] - s_occ) < 3e-5)
        ck(f"ready contrast bin {i}", abs(s["NSYRY"] - c["NSYRY"] + (s_occ - c_occ)) < 3e-5)
        ck(f"unavailable contrast bin {i}", abs(s["NSYUA"] - c["NSYUA"] - (s_occ - c_occ)) < 3e-5)
        ck(f"PM flags bin {i}", c["NPMS"] == int(i in (48, 98)) and c["NPMT"] == int(i in (50, 100)) and s["NPMS"] == int(i in (48, 104)) and s["NPMT"] == int(i in (56, 112)))
        for key in set(c) - changed:
            ck(f"unchanged system {key} bin {i}", c[key] == s[key])
    ck("control PM hours", abs(sum(r["NSYPM"] for r in cs) * .5 - 2) < 3e-5)
    ck("scaled PM hours", abs(sum(r["NSYPM"] for r in ss) * .5 - 8) < 3e-5)
    ck("terminal ready", all(x[-1]["NSYRY"] == x[-1]["NSYA"] == 1 and x[-1]["NSYPM"] == 0 for x in (cs, ss)))
    return {"schema": "simlox-j09-var05-pmt-pair-author-validation/v1", "case_id": "J09", "variant_id": "J09.var05",
            "passed": not failures, "checks": checks, "differences": failures,
            "control_closure_sha256": sha(RUNS["control"] / "closure.json"),
            "scaled_closure_sha256": sha(RUNS["scaled"] / "closure.json"),
            "observed_pm": {arm: {"starts": value[0], "completions": value[1], "planned_hours": value[2]} for arm, value in event_times.items()},
            "scope": "task-free PMLocation.PMT=1 CAL24 PM; SCPMT 1 versus 2; one seed and 60-hour horizon",
            "publication_state": "not_published"}


if __name__ == "__main__":
    result = validate()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
