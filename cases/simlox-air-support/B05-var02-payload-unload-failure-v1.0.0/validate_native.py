"""Author replay of sealed B05.var02 failed-mission unloading pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {
    "ordinary-control": ("b05-var02-failure-ordinary-20260930-01", "d285dad7b2abf887898c516d93b978c0bc6eb1c1a361241ab36e167ca41a83b7"),
    "unloading": ("b05-var02-failure-unloading-20260930-01", "e499bbfc3e76df8038529ec74a74012574c49fd770ac6f3564ee263a518c1bdf"),
}
AIR = "<TEACH-AIR-01,0>"
MISSION = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok: bool, label: str) -> None:
    if not ok:
        raise ValueError(label)


def event(log: str, hour: str, body: str) -> None:
    pattern = rf"^Time: {re.escape(hour)} {re.escape(body)}(?:$|[,: ])"
    require(len(re.findall(pattern, log, re.M)) == 1, f"event {hour} {body}")


def table(report: dict, name: str) -> list[dict]:
    obj = next(t for t in report["report"]["tables"] if t["name"] == name)
    keys = [c["name"] for c in obj["columns"]]
    return [dict(zip(keys, row)) for i in obj["instances"] for row in i["rows"]]


def one(variant: str) -> dict:
    run_id, input_sha = RUNS[variant]
    run = HERE / "runs" / run_id
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "stable sealed source")
    require(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    require(invocation["case_id"] == "B05.var02" and invocation["case_version"] == "1.0.0-candidate", "case identity")
    require(invocation["variant"] == variant and invocation["input_sha256"] == input_sha, "input identity")
    require(invocation["session_id"] == 0 and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "session and GUI")
    require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host queue")
    sources = {"input": HERE / f"{variant}-input.json",
               "parent": HERE.parent / "B05-var02-payload-unload-success-v1.0.0" / "ordinary-control-input.json",
               "failure_source": HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json",
               "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
               "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        require(sha(path) == closure["source_hashes_before"][name], f"source SHA {name}")
    for name, record in closure["raw"].items():
        require((run / name).stat().st_size == record["bytes"] and sha(run / name) == record["sha256"], f"raw SHA {name}")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "native step names")
    require(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "native step outcomes")
    rt = roundtrip(run)
    require(rt["passed"] and len(rt["populated_tables"]) == 19, "19-table roundtrip")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "Total execution time:" in calc, "native conversion/calc")
    require(sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "known warnings")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for hour, body in [
        ("7", f" payloading subtask 0 seqno 1 within system preparation task 0 on {AIR} starts performing, planned to last for 0.166667 hours"),
        ("7.16667", f" payloading subtask 0 seqno 1 within system preparation task 0 on {AIR} completed"),
        ("8", f"{MISSION} mission starting"),
        ("9.8829", f"{AIR} critical random failure added"),
        ("9.8829", f"{MISSION} mission aborted"),
        ("10", f"{MISSION} aborted mission completed"),
        ("10", f"{AIR} turnround started, mission: {MISSION}"),
        ("10.1667", f"{AIR} turnround ended, mission: {MISSION}"),
        ("10.1667", f" direct repair subtask 3 seqno 0 within system DIRP task 2 on {AIR} starts performing, planned to last for 0.5 hours"),
        ("10.6667", f" direct repair subtask 3 seqno 0 within system DIRP task 2 on {AIR} completed"),
        ("10.6667", f"{AIR} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>"),
    ]:
        event(log, hour, body)
    first = "unloading subtask" if variant == "unloading" else "subtask"
    event(log, "10", f" {first} 2 seqno 1 within system turnround task 1 on {AIR} starts performing, planned to last for 0.166667 hours")
    event(log, "10.1667", f" {first} 2 seqno 1 within system turnround task 1 on {AIR} completed")
    require("unloading subtask 2 seqno 1 within system turnround task 1 on " + AIR + " skipped" not in log, "unloading not skipped")
    require("mission success" not in log, "aborted mission not success")
    report = parse_native(run / "report-raw.json")
    summary, system, stock = (table(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    require(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36 and summary[0]["MSUF"] == 0, "report summary")
    require(len(system) == len(stock) == 72, "report bins")
    require(sum(r["NFAIL"] for r in system) == sum(r["NREPT"] for r in system) == 1, "failure and repair totals")
    ten = next(r for r in system if r["STINT"] == 10)
    require(abs(ten["NSYMT"]-1/3) < 2e-5 and abs(ten["NSYRP"]-2/3) < 2e-5, "return and repair exposure")
    require(system[-1]["STINT"] == 35.5 and system[-1]["NSYRY"] == system[-1]["NSYA"] == 1, "terminal ready")
    return {"variant": variant, "run_id": run_id, "input_sha256": input_sha,
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "source_roundtrip": True, "native_steps": 5,
            "system_bins": len(system), "stock_bins": len(stock), "terminal_ready": system[-1]["NSYRY"]}


def main() -> None:
    result = {variant: one(variant) for variant in RUNS}
    a, b = (parse_native(HERE / "runs" / RUNS[v][0] / "report-raw.json") for v in RUNS)
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        require(table(a, name) == table(b, name), f"paired report {name}")
    output = {"schema": "simlox-b05-var02-failure-v100-author-native-validation/v1", "passed": True,
              "runs": result, "scope": "failed payloaded mission: positive built-in UNLOADING versus ordinary equal-duration control, followed by direct repair",
              "publication_state": "candidate_pending_independent_review"}
    target = HERE / "review" / "author-native-validation-2026-09-30.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
