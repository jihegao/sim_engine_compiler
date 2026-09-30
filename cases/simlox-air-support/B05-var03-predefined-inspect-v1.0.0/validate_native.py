"""Author replay of sealed B05.var03 ordinary/predefined inspection pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {
    "ordinary-control": ("b05-var03-ordinary-20260930-01", "37423c0c127a014d082c740780eee8531e877c405bcd537918b8fc1e4289892b"),
    "predefined-inspect": ("b05-var03-predefined-20260930-01", "2fc3b10f9a17db8dc4cc4fa4810d79ef9231775c1fcb658303742ad15e41fc46"),
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


def report_table(doc: dict, name: str) -> list[dict]:
    obj = next(t for t in doc["report"]["tables"] if t["name"] == name)
    fields = [c["name"] for c in obj["columns"]]
    return [dict(zip(fields, row)) for i in obj["instances"] for row in i["rows"]]


def one(variant: str) -> dict:
    run_id, input_sha = RUNS[variant]
    run = HERE / "runs" / run_id
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "source closure")
    require(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    require(invocation["case_id"] == "B05.var03" and invocation["case_version"] == "1.0.0-candidate", "case")
    require(invocation["variant"] == variant and invocation["input_sha256"] == input_sha, "input")
    require(invocation["session_id"] == 0 and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "session GUI")
    require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "queue")
    sources = {"input": HERE / f"{variant}-input.json", "parent": HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json",
               "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
               "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        require(sha(path) == closure["source_hashes_before"][name], f"source {name}")
    for name, record in closure["raw"].items():
        require((run / name).stat().st_size == record["bytes"] and sha(run / name) == record["sha256"], f"raw {name}")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "steps")
    require(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "step result")
    rt = roundtrip(run)
    require(rt["passed"] and len(rt["populated_tables"]) == 17, "17-table exact roundtrip")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "Total execution time:" in calc, "conversion/calc")
    require(sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "expected warnings")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for hour, body in [
        ("7", f" subtask 0 seqno 1 within system preparation task 0 on {AIR} starts performing, planned to last for 0.166667 hours"),
        ("7.16667", f" subtask 0 seqno 1 within system preparation task 0 on {AIR} completed"),
        ("7.16667", f" subtask 1 seqno 2 within system preparation task 0 on {AIR} starts performing, planned to last for 0.333333 hours"),
        ("7.5", f" subtask 1 seqno 2 within system preparation task 0 on {AIR} completed"),
        ("7.5", f"{AIR} preparation ended, mission: {MISSION}"),
        ("8", f"{MISSION} mission starting"), ("10", f"{MISSION} mission success"),
        ("10", f"{MISSION} mission completed"), ("10", f"{AIR} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>"),
    ]:
        event(log, hour, body)
    report = parse_native(run / "report-raw.json")
    summary, system, stock = (report_table(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    require(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36, "summary")
    require(len(system) == len(stock) == 72 and system[-1]["STINT"] == 35.5, "72 half-hour bins")
    require(system[-1]["NSYRY"] == system[-1]["NSYA"] == 1, "terminal ready")
    return {"variant": variant, "run_id": run_id, "input_sha256": input_sha,
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "source_roundtrip": True,
            "native_steps": 5, "system_bins": len(system), "stock_bins": len(stock)}


def main() -> None:
    result = {variant: one(variant) for variant in RUNS}
    require(result["ordinary-control"]["model_log_sha256"] == result["predefined-inspect"]["model_log_sha256"], "byte-identical event logs")
    a, b = (parse_native(HERE / "runs" / RUNS[v][0] / "report-raw.json") for v in RUNS)
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        require(report_table(a, name) == report_table(b, name), f"paired {name}")
    output = {"schema": "simlox-b05-var03-v100-author-native-validation/v1", "passed": True,
              "runs": result, "scope": "one mission-preparation <INSPECT> reference with same event log and report data as ordinary custom INSPECT",
              "publication_state": "candidate_pending_independent_review"}
    target = HERE / "review" / "author-native-validation-2026-09-30.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
