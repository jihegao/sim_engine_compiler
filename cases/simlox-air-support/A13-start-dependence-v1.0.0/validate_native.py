"""Validate immutable A13 paired native evidence and the START launch gate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
RUN_IDS = {"control": "a13-control-20260930-03", "dependent": "a13-dependent-20260930-03"}
SOURCES = {"control": "fcfa0c086085bfca72b49afe922f6968ec1d1597354cedb7e0c1230a1f5be42f", "dependent": "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"}
EVENT = re.compile(r"^Time: ([0-9.]+) <(RECON|FOLLOW),TEACH-UNIT,0,0,\d+> (mission allocates system|mission starting|mission success|mission completed)[,:] ?(.*)$", re.M)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_eq(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in table["columns"]], [r for i in table["instances"] for r in i["rows"]]


def validate_one(variant: str) -> dict:
    run = RUNS / RUN_IDS[variant]
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    assert_eq(closure["error"], None, "closure error")
    assert_eq(invocation["variant"], variant, "invocation variant")
    assert_eq(invocation["session_id"], 0, "SSH session")
    assert_eq(invocation["gui"]["pid"], 13340, "preserved GUI PID")
    assert_eq(invocation["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "host mutex")
    assert_eq(sha(run / "invocation.json"), closure["invocation_sha256"], "invocation SHA")
    assert_eq(invocation["input_sha256"], SOURCES[variant], "invocation source SHA")
    assert_eq(closure["source_hashes_before"], closure["source_hashes_after"], "stable source hashes")
    for name, path in {
        "input": HERE / f"{variant}-input.json",
        "parent": HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json",
        "contract": HERE / "contract.json",
        "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py",
        "runner_script": HERE / "run_native_ssh.ps1",
    }.items():
        assert_eq(sha(path), closure["source_hashes_before"][name], f"source {name} SHA")
    for name, info in closure["raw"].items():
        path = run / name
        assert_eq(path.stat().st_size, info["bytes"], f"raw {name} bytes")
        assert_eq(sha(path), info["sha256"], f"raw {name} SHA")
    assert_eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "native steps")
    if any(s["status"] != "completed" or s["exit_code"] != 0 or s["gui_preserved"] is not True for s in steps):
        raise ValueError("a native step did not complete with GUI preserved")
    roundtrip = check_roundtrip(run)
    if not roundtrip["passed"]:
        raise ValueError(f"roundtrip failed: {roundtrip['differences']}")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if not re.search(r"Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0", calc):
        raise ValueError("conversion counts differ")
    if sorted(set(map(int, re.findall(r"warning #(\d+)", calc)))) != [108, 126]:
        raise ValueError("unexpected native warning codes")
    if "Total execution time:" not in calc or "Saving results" not in calc:
        raise ValueError("calculation completion absent")
    report = parse_native(run / "report-raw.json")
    cols, summary_rows = rows(report, "ResultSummary")
    if len(summary_rows) != 1:
        raise ValueError("summary cardinality")
    summary = dict(zip(cols, summary_rows[0]))
    for field, expected in {"NREP": 1, "RTILW": 0, "RTIUP": 24, "MSTF": 1, "MSUF": 1, "STMF": 1}.items():
        assert_eq(summary[field], expected, f"ResultSummary.{field}")
    cols, system_rows = rows(report, "SystemResults")
    if len(system_rows) != 48:
        raise ValueError("expected 48 half-hour system bins")
    if len(rows(report, "StockTotalResults")[1]) != 48:
        raise ValueError("expected 48 stock bins")
    i = {name: cols.index(name) for name in ("STINT", "ETINT", "NSYMO")}
    at_ten = next(r for r in system_rows if r[i["STINT"]] == 10 and r[i["ETINT"]] == 10.5)
    assert_eq(at_ten[i["NSYMO"]], 2 if variant == "control" else 1, "systems on mission at hour 10")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    events: dict[str, dict[str, list[tuple[float, str]]]] = {"RECON": {}, "FOLLOW": {}}
    for match in EVENT.finditer(log):
        time, mission, kind, detail = match.groups()
        events[mission].setdefault(kind, []).append((float(time), detail))
    for mission, aircraft in (("RECON", "<TEACH-AIR-01,0>"), ("FOLLOW", "<TEACH-AIR-01,1>")):
        allocations = events[mission].get("mission allocates system", [])
        if len(allocations) != 1 or allocations[0][1] != aircraft:
            raise ValueError(f"{mission} aircraft assignment differs")
        for kind in ("mission starting", "mission success", "mission completed"):
            if len(events[mission].get(kind, [])) != 1:
                raise ValueError(f"{mission} {kind} cardinality differs")
    expected_start = 10.0 if variant == "control" else 12.0
    assert_eq(events["RECON"]["mission starting"][0][0], 8.0, "RECON start")
    assert_eq(events["RECON"]["mission success"][0][0], 12.0, "RECON logged success")
    assert_eq(events["RECON"]["mission completed"][0][0], 12.0, "RECON completion")
    assert_eq(events["FOLLOW"]["mission allocates system"][0][0], 9.0, "FOLLOW allocation")
    assert_eq(events["FOLLOW"]["mission starting"][0][0], expected_start, "FOLLOW start")
    assert_eq(events["FOLLOW"]["mission success"][0][0], expected_start + 2, "FOLLOW success")
    assert_eq(events["FOLLOW"]["mission completed"][0][0], expected_start + 2, "FOLLOW completion")
    return {"variant": variant, "run_id": RUN_IDS[variant], "closure_sha256": sha(run / "closure.json"), "roundtrip_tables": len(roundtrip["populated_tables"]), "start_hours": {"RECON": 8, "FOLLOW": expected_start}, "follow_allocated_hour": 9, "reported_system_bins": 48, "reported_stock_bins": 48, "warnings": [108, 126]}


def main() -> int:
    try:
        result = {v: validate_one(v) for v in ("control", "dependent")}
        assert_eq(result["dependent"]["start_hours"]["FOLLOW"] - result["control"]["start_hours"]["FOLLOW"], 2.0, "START dependency delay")
        output = {"schema": "simlox-a13-start-dependence-v100-author-validation/v1", "passed": True, "native_scope": "one explicit START dependence with one predecessor in one unit", "variants": result}
    except (OSError, KeyError, IndexError, StopIteration, TypeError, ValueError) as error:
        output = {"schema": "simlox-a13-start-dependence-v100-author-validation/v1", "passed": False, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(output, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
