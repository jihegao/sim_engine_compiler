"""Validate the frozen C05 native run's bounded, observed resource ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
EXPECTED_SHA = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))["input_sha256"]
EXPECTED = {
    2: {"assigned": 2, "released": 2, "mission_started": 1, "mission_succeeded": 1, "cancelled": 0},
    1: {"assigned": 1, "released": 1, "mission_started": 0, "mission_succeeded": 0, "cancelled": 1},
    0: {"assigned": 0, "released": 0, "mission_started": 0, "mission_succeeded": 0, "cancelled": 1},
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(doc: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [r for i in table["instances"] for r in i["rows"]]


def check(capacity: int) -> dict:
    run = HERE / "runs" / f"c05-capacity-{capacity}-20260930-01"
    issues: list[str] = []
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    source = HERE / f"capacity-{capacity}-input.json"
    expect_sha = EXPECTED_SHA[f"capacity-{capacity}"]
    if sha(source) != expect_sha or sha(run / "input.json") != expect_sha:
        issues.append("frozen input hash mismatch")
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
        issues.append("native closure error or source drift")
    if len(steps) != 5 or any(s["status"] != "completed" or s["exit_code"] != 0 or not s["gui_preserved"] for s in steps):
        issues.append("native step or GUI preservation failed")
    for name, item in closure["raw"].items():
        path = run / name
        if not path.is_file() or sha(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            issues.append(f"raw seal mismatch: {name}")
    if populated(parse_native(source)) != {name: table for name, table in populated(parse_native(run / "roundtrip-raw.json")).items() if name in populated(parse_native(source))}:
        issues.append("populated source tables differ after native roundtrip")
    if not json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"]:
        issues.append("roundtrip checker failed")
    for filename in ("import.log", "run.log", "export.log", "report-export.log"):
        log = (run / filename).read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"\(error\s+#\d+\)", log, re.I):
            issues.append(f"converter error in {filename}")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    warnings = sorted(set(re.findall(r"warning\s+#(\d+)", run_log, re.I)))
    if warnings != ["108", "126"]:
        issues.append(f"unexpected warnings {warnings}")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    assigned = re.findall(r"Time: 7\s+<MISSION-CREW at <BASE-01,0>> allocated to mission assigned: 1\s+available now: (\d+)", log)
    released = re.findall(r"Time: (?:10|8\.33333)\s+<MISSION-CREW at <BASE-01,0>> deallocated from\s+mission (?:operation|assigned): 1\s+available now: (\d+)", log)
    observed = {
        "assigned": len(assigned),
        "released": len(released),
        "mission_started": len(re.findall(r"Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", log)),
        "mission_succeeded": len(re.findall(r"Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", log)),
        "cancelled": len(re.findall(r"Time: 8\.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled", log)),
    }
    if observed != EXPECTED[capacity]:
        issues.append(f"event counts differ: {observed}")
    if capacity == 2 and released != ["1", "2"]:
        issues.append("capacity-2 release balance differs")
    if capacity == 1 and (assigned != ["0"] or released != ["1"] or "request for: 1 failed" not in log):
        issues.append("capacity-1 reservation/wait/release ledger differs")
    if capacity == 0 and (assigned or released or log.count("request for: 1 failed") < 2):
        issues.append("capacity-0 shortage ledger differs")
    if capacity in (1, 0) and "mission waiting:  timeout at 8.33333" not in log:
        issues.append("shortage timeout absent")
    if capacity in (2, 1) and f"systems ready: 2 :" not in log:
        issues.append("two-aircraft readiness absent")
    report = parse_native(run / "report-raw.json")
    summary_cols, summary_rows = rows(report, "ResultSummary")
    if len(summary_rows) != 1 or summary_rows[0][summary_cols.index("MTMF")] != (1 if capacity == 2 else 0):
        issues.append("mission total metric differs")
    resource_cols, resource_rows = rows(report, "ResourceResultsTotal")
    if len(resource_rows) != 1 or resource_rows[0][resource_cols.index("NR")] != capacity:
        issues.append("resource total capacity differs")
    system_cols, system_rows = rows(report, "SystemResults")
    if len(system_rows) != 72 or system_rows[-1][system_cols.index("NSYRY")] != 2:
        issues.append("terminal two-aircraft readiness differs")
    stock_cols, stock_rows = rows(report, "StockTotalResults")
    if len(stock_rows) != 72 or any(row[stock_cols.index(name)] != 0 for row in stock_rows for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
        issues.append("unexpected inventory movement or invalid stock report")
    _, resource_interval_rows = rows(report, "ResourceResults")
    if len(resource_interval_rows) != 72:
        issues.append("resource time-series report incomplete")
    return {
        "capacity": capacity,
        "passed": not issues,
        "issues": issues,
        "observed": observed,
        "warnings": warnings,
        "source_sha256": expect_sha,
        "closure_sha256": sha(run / "closure.json"),
        "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
    }


def main() -> int:
    variants = [check(c) for c in (2, 1, 0)]
    output = {"schema": "simlox-c05-native-author-validation/v1", "case_id": "C05", "passed": all(x["passed"] for x in variants), "variants": variants, "rejected_pre_run_hypothesis": "capacity 1 does partially reserve a resource and assign one aircraft before formation cancellation", "scope": "three fixed-capacity deterministic native CLI runs; broader C05 open"}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
