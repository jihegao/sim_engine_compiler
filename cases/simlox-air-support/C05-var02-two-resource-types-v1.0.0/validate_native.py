"""Validate observed C05.var02 all-types mission-resource native behavior."""

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


def check(radio: int) -> dict:
    issues: list[str] = []
    run = HERE / "runs" / f"c05-var02-radio-{radio}-20260930-01"
    source = HERE / f"radio-{radio}-input.json"
    expected_input_sha = INPUT_SHA[f"radio-{radio}"]
    if sha(source) != expected_input_sha or sha(run / "input.json") != expected_input_sha:
        issues.append("input fingerprint differs")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    if invocation["variant"] != f"radio-{radio}" or invocation["session_id"] != 0 or not invocation["ssh_connection_present"] or "sshd.exe" not in invocation["ssh_ancestor_names"]:
        issues.append("guarded SSH provenance differs")
    if invocation["queue_mutex"] != "Global\\SimloxIssue18NativeQueue" or invocation["gui"]["pid"] != 13340 or invocation["gui"]["session_id"] != 1:
        issues.append("GUI or mutex provenance differs")
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
        issues.append("closure error/source drift")
    if len(steps) != 5 or any(step["status"] != "completed" or step["exit_code"] != 0 or not step["gui_preserved"] for step in steps):
        issues.append("native step failure/GUI drift")
    for name, item in closure["raw"].items():
        path = run / name
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha(path) != item["sha256"]:
            issues.append(f"raw seal differs: {name}")
    source_tables = populated(parse_native(source))
    after_tables = populated(parse_native(run / "roundtrip-raw.json"))
    if len(source_tables) != 16 or any(after_tables.get(name) != value for name, value in source_tables.items()):
        issues.append("populated table roundtrip differs")
    if not json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"]:
        issues.append("roundtrip checker failed")
    warnings: set[str] = set()
    for filename in ("import.log", "export.log", "run.log", "report-export.log"):
        log = (run / filename).read_text(encoding="utf-8-sig", errors="replace")
        if re.search(r"\(error\s+#\d+\)", log, re.I):
            issues.append(f"native conversion error: {filename}")
        warnings.update(re.findall(r"warning\s+#(\d+)", log, re.I))
    if warnings != {"108", "126"}:
        issues.append(f"unexpected warning set: {sorted(warnings)}")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    crew_ok = len(re.findall(r"Availability test on\s+<MISSION-CREW at <BASE-01,0>> request for: 1 OK", log))
    radio_status = len(re.findall(r"Availability test on\s+<MISSION-RADIO at <BASE-01,0>> request for: 1 " + ("OK" if radio == 2 else "failed"), log))
    assignments = {rid: len(re.findall(rf"<MISSION-{rid} at <BASE-01,0>> allocated to mission assigned: 1", log)) for rid in ("CREW", "RADIO")}
    releases = {rid: len(re.findall(rf"<MISSION-{rid} at <BASE-01,0>> deallocated from\s+mission operation: 1", log)) for rid in ("CREW", "RADIO")}
    if crew_ok != 2 or radio_status != 2 or assignments != {"CREW": radio, "RADIO": radio} or releases != {"CREW": radio, "RADIO": radio}:
        issues.append("two-type resource availability/allocation/release ledger differs")
    starts = len(re.findall(r"Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", log))
    succeeds = len(re.findall(r"Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", log))
    cancels = len(re.findall(r"Time: 8\.33333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled", log))
    if (starts, succeeds, cancels) != ((1, 1, 0) if radio == 2 else (0, 0, 1)):
        issues.append("mission event outcome differs")
    if radio == 2 and ("[MISSION-CREW 1][MISSION-RADIO 1]" not in log or "systems ready: 2 :" not in log):
        issues.append("two-resource mission/terminal event differs")
    if radio == 0 and "mission waiting:  timeout at 8.33333" not in log:
        issues.append("shortage wait/deadline absent")
    report = parse_native(run / "report-raw.json")
    cols, rr = report_table(report, "ResultSummary")
    if len(rr) != 1 or rr[0][cols.index("MTMF")] != (1 if radio == 2 else 0):
        issues.append("mission result metric differs")
    cols, rr = report_table(report, "ResourceResultsTotal")
    if len(rr) != 1 or rr[0][cols.index("NR")] != 2 + radio:
        issues.append("total resource capacity metric differs")
    cols, rr = report_table(report, "SystemResults")
    if len(rr) != 72 or rr[-1][cols.index("NSYRY")] != 2:
        issues.append("system time series/terminal readiness differs")
    cols, rr = report_table(report, "StockTotalResults")
    if len(rr) != 72 or any(row[cols.index(name)] != 0 for row in rr for name in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT")):
        issues.append("stock report/inventory movement differs")
    _, rr = report_table(report, "ResourceResults")
    if len(rr) != 72:
        issues.append("resource time series incomplete")
    return {"radio_capacity": radio, "passed": not issues, "issues": issues, "crew_availability_ok": crew_ok, "radio_availability_expected": radio_status, "assignments": assignments, "releases": releases, "mission_events": {"started": starts, "succeeded": succeeds, "cancelled": cancels}, "warnings": sorted(warnings), "source_sha256": expected_input_sha, "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"), "report_sha256": sha(run / "report-raw.json")}


def main() -> int:
    variants = [check(x) for x in (2, 0)]
    result = {"schema": "simlox-c05-var02-author-validation/v1", "case_id": "C05", "variant_id": "C05.var02", "passed": all(x["passed"] for x in variants), "variants": variants, "scope": "two fixed-seed two-resource-type native CLI observations; broader C05 open"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
