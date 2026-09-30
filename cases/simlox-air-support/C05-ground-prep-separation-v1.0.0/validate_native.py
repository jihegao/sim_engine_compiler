"""Validate fixed C05 ground-preparation versus mission-resource native evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
INPUT_SHA = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))["input_sha256"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [row for i in table["instances"] for row in i["rows"]]


def count(pattern: str, log: str) -> int:
    return len(re.findall(pattern, log))


def check(ground: int) -> dict:
    issues: list[str] = []
    run = HERE / "runs" / f"c05-ground-{ground}-20260930-01"
    source = HERE / f"ground-{ground}-input.json"
    expected_sha = INPUT_SHA[f"ground-{ground}"]
    if sha(source) != expected_sha or sha(run / "input.json") != expected_sha:
        issues.append("frozen input fingerprint differs")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    if invocation["variant"] != f"ground-{ground}" or invocation["session_id"] != 0 or not invocation["ssh_connection_present"] or "sshd.exe" not in invocation["ssh_ancestor_names"]:
        issues.append("SSH provenance differs")
    if invocation["queue_mutex"] != "Global\\SimloxIssue18NativeQueue" or invocation["gui"]["pid"] != 13340 or invocation["gui"]["session_id"] != 1:
        issues.append("queue/GUI provenance differs")
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
        issues.append("closure error or source drift")
    if len(steps) != 5 or any(s["status"] != "completed" or s["exit_code"] != 0 or not s["gui_preserved"] for s in steps):
        issues.append("native step/GUI preservation failure")
    for name, item in closure["raw"].items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            issues.append(f"raw seal differs: {name}")
    before = populated(parse_native(source))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    if len(before) != 19 or any(after.get(name) != table for name, table in before.items()):
        issues.append("populated source table roundtrip differs")
    if not json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"]:
        issues.append("roundtrip checker failed")
    warnings: set[str] = set()
    for name in ("import.log", "export.log", "run.log", "report-export.log"):
        log = (run / name).read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"\(error\s+#\d+\)", log, re.I):
            issues.append(f"native conversion error: {name}")
        warnings.update(re.findall(r"warning\s+#(\d+)", log, re.I))
    if warnings != {"108", "126"}:
        issues.append(f"unexpected warnings: {sorted(warnings)}")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    observed = {
        "crew_assigned_h7": count(r"Time: 7\s+<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1", log),
        "ground_task_alloc_h7": count(r"Time: 7\s+<GROUND-TECH at <BASE-01,0>> allocated to maintenance task: 1", log),
        "ground_task_release_h7_5": count(r"Time: 7\.5\s+<GROUND-TECH at <BASE-01,0>> deallocated from\s+maintenance task: 1", log),
        "crew_mission_release_h10": count(r"Time: 10\s+<MISSION-CREW at <BASE-01,0>> deallocated from\s+mission operation: 1", log),
        "crew_assignment_release_h7_83333": count(r"Time: 7\.83333\s+<MISSION-CREW at <BASE-01,0>> deallocated from\s+mission assigned: 1", log),
        "mission_start_h8": count(r"Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", log),
        "mission_success_h10": count(r"Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", log),
        "mission_cancel_h7_83333": count(r"Time: 7\.83333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled", log),
    }
    expected = {"crew_assigned_h7": 2, "ground_task_alloc_h7": ground, "ground_task_release_h7_5": ground, "crew_mission_release_h10": ground, "crew_assignment_release_h7_83333": 0 if ground == 2 else 2, "mission_start_h8": 1 if ground == 2 else 0, "mission_success_h10": 1 if ground == 2 else 0, "mission_cancel_h7_83333": 0 if ground == 2 else 1}
    if observed != expected:
        issues.append(f"separate resource event ledger differs: {observed}")
    if ground == 2:
        if count(r"Time: 7\.5 <TEACH-AIR-01,[01]> preparation ended", log) != 2 or "[MISSION-CREW 1]" not in log:
            issues.append("successful preparation/mission resource boundary differs")
    else:
        if count(r"Availability test on\s+<GROUND-TECH at <BASE-01,0>> request for: 1 failed", log) < 2 or count(r"resource waiting stopped", log) != 2:
            issues.append("ground shortage/stop behavior differs")
    if not re.search(r"systems ready: 2 :<TEACH-AIR-01,[01]>,<TEACH-AIR-01,[01]>", log):
        issues.append("two-aircraft ready state absent")
    report = parse_native(run / "report-raw.json")
    cols, rr = report_table(report, "ResultSummary")
    if len(rr) != 1 or rr[0][cols.index("MTMF")] != (1 if ground == 2 else 0):
        issues.append("mission metric differs")
    cols, rr = report_table(report, "ResourceResultsTotal")
    if len(rr) != 1 or rr[0][cols.index("NR")] != 2 + ground:
        issues.append("resource total metric differs")
    cols, rr = report_table(report, "SystemResults")
    if len(rr) != 72 or rr[-1][cols.index("NSYRY")] != 2:
        issues.append("system time series/terminal readiness differs")
    cols, rr = report_table(report, "StockTotalResults")
    if len(rr) != 72 or any(row[cols.index(name)] != 0 for row in rr for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
        issues.append("stock report/inventory movement differs")
    _, rr = report_table(report, "ResourceResults")
    if len(rr) != 72:
        issues.append("resource time series incomplete")
    return {"ground_capacity": ground, "passed": not issues, "issues": issues, "observed": observed, "warnings": sorted(warnings), "source_sha256": expected_sha, "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json")}


def main() -> int:
    variants = [check(x) for x in (2, 0)]
    result = {"schema": "simlox-c05-ground-prep-author-validation/v1", "case_id": "C05", "passed": all(x["passed"] for x in variants), "variants": variants, "scope": "two fixed-capacity ground preparation versus mission resource native CLI runs; broader C05 open"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
