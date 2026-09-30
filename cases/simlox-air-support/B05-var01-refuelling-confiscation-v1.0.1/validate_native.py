"""Author replay of the sealed B05.var01 v1.0.1 native pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {
    "inspect-control": ("b05-var01-v101-inspect-control-20260930-01", "06985a6e5b4ddc413ad9c26b5ce31857bbb89261ceb69b8d68a852edb2510743"),
    "refuelling": ("b05-var01-v101-refuelling-20260930-01", "025651d2f6cef2636a77de88c0771e49cdef20ca63a73542415d4214f662da90"),
}
AIR = "<TEACH-AIR-01,0>"
BASIC0 = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
BASIC1 = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
SECOND = "<SECOND-MISSION,TEACH-UNIT,0,0,2>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, label: str) -> None:
    if not ok:
        raise ValueError(label)


def event(log: str, hour: str, body: str) -> None:
    pattern = rf"^Time: {re.escape(hour)} {re.escape(body)}(?:$|[,: ])"
    require(len(re.findall(pattern, log, re.M)) == 1, f"event {hour} {body}")


def report_table(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def one(variant: str) -> dict:
    run_id, source_sha = RUNS[variant]
    run = HERE / "runs" / run_id
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "closure/source stable")
    require(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    require(invocation["variant"] == variant and invocation["input_sha256"] == source_sha, "invocation source")
    require(invocation["case_version"] == "1.0.1-candidate" and invocation["session_id"] == 0, "version/session")
    require(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI identity")
    require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "native queue")
    sources = {"input": HERE / f"{variant}-input.json", "parent": HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json",
               "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
               "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        require(sha(path) == closure["source_hashes_before"][name], f"sealed source {name}")
    for name, record in closure["raw"].items():
        require((run / name).stat().st_size == record["bytes"] and sha(run / name) == record["sha256"], f"sealed raw {name}")
    require([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "native steps")
    require(all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps), "native step result")
    rt = roundtrip(run)
    require(rt["passed"] and len(rt["populated_tables"]) == 17, "exact source roundtrip")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "Total execution time:" in calc, "conversion/simulation")
    require(sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "expected warnings")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for hour, body in [
        ("1", "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        ("2", f"{BASIC0} mission starting"), ("4", f"{BASIC0} mission success"),
        ("7", "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
        ("7", f"{BASIC1} mission allocates system: {AIR}"),
        ("7.25", "<TEACH-UNIT> mission ordered: SECOND-MISSION"),
        ("7.25", f"{BASIC1} mission gives away system: {AIR}"),
        ("7.25", f"{SECOND} mission allocates system: {AIR}"),
        ("7.25", f"{AIR} preparation started, mission: {SECOND}"),
        ("8.25", f"{SECOND} mission starting"),
        ("10.25", f"{SECOND} mission success"),
        ("10.25", f"{SECOND} mission completed"),
    ]:
        event(log, hour, body)
    first = "refuelling subtask" if variant == "refuelling" else "subtask"
    event(log, "7", f" refuelling subtask 2 seqno 1 within system preparation task 1 on {AIR} starts performing, planned to last for 0.166667 hours" if variant == "refuelling" else f" subtask 2 seqno 1 within system preparation task 1 on {AIR} starts performing, planned to last for 0.166667 hours")
    event(log, "7.16667", f" {first} 2 seqno 1 within system preparation task 1 on {AIR} completed")
    event(log, "7.16667", f" subtask 3 seqno 2 within system preparation task 1 on {AIR} starts performing, planned to last for 0.333333 hours")
    event(log, "7.25", f" subtask 3 seqno 2 within system preparation task 1 on {AIR} ordered to stop")
    if variant == "refuelling":
        event(log, "7.25", f" refuelling subtask 4 seqno 1 within system preparation task 2 on {AIR} skipped")
        require(len(re.findall(r"refuelling subtask 4 seqno 1 within system preparation task 2", log)) == 1, "no child refuelling work")
        service_start, prep_end, cancel = "7.25", "7.58333", "7.58333"
    else:
        event(log, "7.25", f" subtask 4 seqno 1 within system preparation task 2 on {AIR} starts performing, planned to last for 0.166667 hours")
        event(log, "7.41667", f" subtask 4 seqno 1 within system preparation task 2 on {AIR} completed")
        service_start, prep_end, cancel = "7.41667", "7.75", "7.58333"
    event(log, service_start, f" subtask 5 seqno 2 within system preparation task 2 on {AIR} starts performing, planned to last for 0.333333 hours")
    event(log, prep_end, f" subtask 5 seqno 2 within system preparation task 2 on {AIR} completed")
    event(log, prep_end, f"{AIR} preparation ended, mission: {SECOND}")
    event(log, cancel, f"{BASIC1} mission cancelled")
    report = parse_native(run / "report-raw.json")
    summary = report_table(report, "ResultSummary")
    system = report_table(report, "SystemResults")
    stock = report_table(report, "StockTotalResults")
    require(len(summary) == 1 and len(system) == len(stock) == 72, "report row count")
    require(summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36, "report horizon")
    require(all(abs(row["ETINT"]-row["STINT"]-0.5) < 1e-6 for row in system), "report bins")
    require(system[-1]["STINT"] == 35.5 and system[-1]["NSYRY"] == system[-1]["NSYA"] == 1, "terminal readiness")
    at_75 = next(row for row in system if row["STINT"] == 7.5)
    expected_prep = 1/6 if variant == "refuelling" else 1/2
    require(abs(at_75["NSYMP"] - expected_prep) < 2e-5 and abs(at_75["NSYMR"] - (1-expected_prep)) < 2e-5, "report preparation/mission ready bin")
    return {"variant": variant, "run_id": run_id, "input_sha256": source_sha,
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "source_roundtrip": True,
            "native_steps": 5, "report_system_bins": len(system), "report_stock_bins": len(stock),
            "prep_fraction_7_5_to_8": at_75["NSYMP"], "ready_for_mission_fraction_7_5_to_8": at_75["NSYMR"],
            "terminal_ready": system[-1]["NSYRY"]}


def main() -> None:
    pair = {variant: one(variant) for variant in RUNS}
    left = parse_native(HERE / "runs" / RUNS["inspect-control"][0] / "report-raw.json")
    right = parse_native(HERE / "runs" / RUNS["refuelling"][0] / "report-raw.json")
    require(report_table(left, "ResultSummary") == report_table(right, "ResultSummary"), "paired summary")
    require(report_table(left, "StockTotalResults") == report_table(right, "StockTotalResults"), "paired stock bins")
    left_system, right_system = report_table(left, "SystemResults"), report_table(right, "SystemResults")
    for a, b in zip(left_system, right_system):
        changed = {key for key in a if a[key] != b[key]}
        require(changed == ({"NSYMP", "NSYMR"} if a["STINT"] == 7.5 else set()), "paired system bin delta")
    out = {"schema": "simlox-b05-var01-v101-author-native-validation/v1", "passed": True, "runs": pair,
           "accepted_scope": "one-aircraft post-flight completed refuelling, active SERVICE confiscation, and explicit refuelling skip for new higher-priority preparation versus repeat INSPECT control",
           "publication_state": "candidate_pending_independent_review"}
    target = HERE / "review" / "author-native-validation-2026-09-30.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
