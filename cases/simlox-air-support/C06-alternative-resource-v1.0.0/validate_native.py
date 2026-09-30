"""Validate C06 fixed alternative-resource selection and time-factor observations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
INPUT_SHA = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))["input_sha256"]
EXPECTED = {
    "primary-2-artf-2": {"resource": "P-CREW", "work_hours": "0.333333", "task_end": "7.83333", "mission_start": "8", "mission_end": "9", "available": 4},
    "primary-0-artf-1": {"resource": "P-ALT", "work_hours": "0.333333", "task_end": "7.83333", "mission_start": "8", "mission_end": "9", "available": 2},
    "primary-0-artf-2": {"resource": "P-ALT", "work_hours": "0.666667", "task_end": "8.16667", "mission_start": "8.16667", "mission_end": "9.16667", "available": 2},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count(pattern: str, log: str) -> int:
    return len(re.findall(pattern, log))


def report_table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [row for instance in table["instances"] for row in instance["rows"]]


def check(variant: str) -> dict:
    expect = EXPECTED[variant]
    issues: list[str] = []
    run = HERE / "runs" / f"c06-{variant}-20260930-01"
    source = HERE / f"{variant}-input.json"
    if sha(source) != INPUT_SHA[variant] or sha(run / "input.json") != INPUT_SHA[variant]:
        issues.append("input source fingerprint differs")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    if invocation["variant"] != variant or invocation["session_id"] != 0 or not invocation["ssh_connection_present"] or "sshd.exe" not in invocation["ssh_ancestor_names"]:
        issues.append("guarded SSH provenance differs")
    if invocation["queue_mutex"] != "Global\\SimloxIssue18NativeQueue" or invocation["gui"]["pid"] != 13340 or invocation["gui"]["session_id"] != 1:
        issues.append("queue/GUI provenance differs")
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
        issues.append("closure error/source drift")
    if len(steps) != 5 or any(s["status"] != "completed" or s["exit_code"] != 0 or not s["gui_preserved"] for s in steps):
        issues.append("native step/GUI preservation failure")
    for name, item in closure["raw"].items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            issues.append(f"raw seal differs: {name}")
    before = populated(parse_native(source))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    if len(before) != 20 or any(after.get(name) != table for name, table in before.items()):
        issues.append("populated table roundtrip differs")
    if not json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"]:
        issues.append("roundtrip checker failed")
    warnings: set[str] = set()
    for name in ("import.log", "export.log", "run.log", "report-export.log"):
        log = (run / name).read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"\(error\s+#\d+\)", log, re.I):
            issues.append(f"native conversion error: {name}")
        warnings.update(re.findall(r"warning\s+#(\d+)", log, re.I))
    if warnings != {"108", "126"}:
        issues.append(f"unexpected warning set: {sorted(warnings)}")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    selected = expect["resource"]
    other = "P-ALT" if selected == "P-CREW" else "P-CREW"
    if count(rf"<{selected} at <BASE-01,0>> allocated to maintenance task: 1", log) != 2 or count(rf"<{other} at <BASE-01,0>> allocated to maintenance task: 1", log) != 0:
        issues.append("selected resource booking differs")
    if count(rf"<{selected} at <BASE-01,0>> deallocated from\s+maintenance task: 1", log) != 2:
        issues.append("selected resource release differs")
    if count(rf"starts performing, planned to last for {expect['work_hours']} hours", log) != 2 or count(rf"Time: {re.escape(expect['task_end'])}\s+subtask \d+ seqno 1 within system preparation task \d+ on <TEACH-AIR-01,[01]> completed", log) != 2:
        issues.append("task duration/completion timing differs")
    if count(rf"Time: {re.escape(expect['mission_start'])} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", log) != 1 or count(rf"Time: {re.escape(expect['mission_end'])} <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", log) != 1:
        issues.append("mission timeline differs")
    if count(r"mission cancelled", log) != 0 or not re.search(r"systems ready: 2 :<TEACH-AIR-01,[01]>,<TEACH-AIR-01,[01]>", log):
        issues.append("mission or terminal state differs")
    report = parse_native(run / "report-raw.json")
    cols, rr = report_table(report, "ResultSummary")
    if len(rr) != 1 or rr[0][cols.index("MTMF")] != 1:
        issues.append("mission result metric differs")
    cols, rr = report_table(report, "ResourceResultsTotal")
    if len(rr) != 1 or rr[0][cols.index("NR")] != expect["available"]:
        issues.append("resource total metric differs")
    cols, rr = report_table(report, "SystemResults")
    if len(rr) != 72 or rr[-1][cols.index("NSYRY")] != 2:
        issues.append("system time series/terminal readiness differs")
    cols, rr = report_table(report, "StockTotalResults")
    if len(rr) != 72 or any(row[cols.index(name)] != 0 for row in rr for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
        issues.append("stock time series/inventory movement differs")
    _, rr = report_table(report, "ResourceResults")
    if len(rr) != 72:
        issues.append("resource time series incomplete")
    return {"variant": variant, "passed": not issues, "issues": issues, "selected_resource": selected, "expected_work_hours": expect["work_hours"], "expected_mission_start": expect["mission_start"], "warnings": sorted(warnings), "source_sha256": INPUT_SHA[variant], "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json")}


def main() -> int:
    variants = [check(name) for name in EXPECTED]
    output = {"schema": "simlox-c06-alternative-resource-author-validation/v1", "case_id": "C06", "passed": all(x["passed"] for x in variants), "variants": variants, "scope": "fixed 20-minute preparation with primary/alternative selection and ARTF one/two; other C06 methods open"}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
