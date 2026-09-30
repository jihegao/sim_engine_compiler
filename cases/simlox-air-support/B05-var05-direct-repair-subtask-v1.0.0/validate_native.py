"""Author replay of the sealed B05.var05 direct repair native run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUN_ID = "b05-var05-direct-20260930-01"
RUN = HERE / "runs" / RUN_ID
PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d01-v100-ssh-20260929-01"
INPUT_SHA = "c2f84ff172d15a6ded2f61d0399edcf53c4e0049168cd69780892e33e4065f2b"


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


def main() -> None:
    invocation = json.loads((RUN / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    require(closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"], "closure")
    require(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    require(invocation["case_id"] == "B05.var05" and invocation["variant"] == "direct-repair" and invocation["input_sha256"] == INPUT_SHA, "identity")
    require(invocation["session_id"] == 0 and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "GUI/session")
    require(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "queue")
    sources = {"input": HERE / "native-input.json", "parent": PARENT / "native-input.json", "contract": HERE / "contract.json",
               "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        require(sha(path) == closure["source_hashes_before"][name], f"source {name}")
    for name, record in closure["raw"].items():
        require((RUN / name).stat().st_size == record["bytes"] and sha(RUN / name) == record["sha256"], f"raw {name}")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "steps")
    require(all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "step result")
    rt = roundtrip(RUN)
    require(rt["passed"] and len(rt["populated_tables"]) == 16, "16-table exact roundtrip")
    calc = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    require("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in calc and "Total execution time:" in calc, "conversion/calc")
    require(sorted(map(int, re.findall(r"warning #(\d+)", calc))) == [108, 126], "expected warnings")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    aircraft = "<TEACH-AIR-01,0>"
    for start, end, task in (("10", "10.5", 0), ("34", "34.5", 1)):
        event(log, start, f" direct repair subtask {task} seqno 1 within system DIRP task {task} on {aircraft} starts performing, planned to last for 0.5 hours")
        event(log, end, f" direct repair subtask {task} seqno 1 within system DIRP task {task} on {aircraft} completed")
        event(log, end, f" system DIRP task {task} on {aircraft} completed")
        event(log, end, f"{aircraft} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>")
    require(log.count("critical random failure added") == 2, "two failures")
    require(len(re.findall(r"^Time: .* mission success:", log, re.M)) == 1 and
            len(re.findall(r"^Time: .* mission aborted:", log, re.M)) == 2, "mission outcomes")
    report = parse_native(RUN / "report-raw.json")
    parent_report = parse_native(PARENT_RUN / "report-raw.json")
    require(report_table(report, "ProblemDescription") != report_table(parent_report, "ProblemDescription"), "description delta")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        require(report_table(report, name) == report_table(parent_report, name), f"parent report {name}")
    summary, system, stock = (report_table(report, n) for n in ("ResultSummary", "SystemResults", "StockTotalResults"))
    require(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36, "summary")
    require(len(system) == len(stock) == 72 and system[-1]["STINT"] == 35.5, "72 bins")
    require(system[-1]["NSYRY"] == system[-1]["NSYA"] == 1, "terminal ready")
    output = {"schema": "simlox-b05-var05-v100-author-native-validation/v1", "passed": True,
              "run_id": RUN_ID, "input_sha256": INPUT_SHA, "closure_sha256": sha(RUN / "closure.json"),
              "report_sha256": sha(RUN / "report-raw.json"), "parent_report_sha256": sha(PARENT_RUN / "report-raw.json"),
              "native_steps": 5, "populated_roundtrip_tables": 16, "system_bins": 72, "stock_bins": 72,
              "scope": "one explicit half-hour direct system <REPAIR> subtask overrides four-hour DIRPT in one fixed-seed case",
              "publication_state": "candidate_pending_independent_review"}
    target = HERE / "review" / "author-native-validation-2026-09-30.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
