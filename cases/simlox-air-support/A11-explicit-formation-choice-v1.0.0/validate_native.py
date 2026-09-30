"""Source-bound replay of A11 explicit-formation choice three-run native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
RUN_IDS = {"ab-high": "a11-form-ab-high-20260930-01", "aa-high": "a11-form-aa-high-20260930-01", "b-missing": "a11-form-b-missing-20260930-01"}
SOURCES = {"ab-high": "483c958b91738e53dbd9a88319707e263addd1c6ecd6a723d749fbfd3aa3a15f", "aa-high": "9d3115f9d6c67414fe9d1813ecd028a8eb88976e6f3f65bbb08384bdba911f3a", "b-missing": "78170c663abfae5112da49ab034b28a0c9274bd46d130e2c5f17f2050b0643c8"}
EXPECTED_AIRCRAFT = {"ab-high": ["<TEACH-AIR-01,0>", "<TEACH-AIR-02,2>"], "aa-high": ["<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"], "b-missing": ["<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>"]}
EXPECTED_FORMATION = {"ab-high": "FORM-AB", "aa-high": "FORM-AA", "b-missing": "FORM-AA"}
EVENT = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,0> (mission allocates system|mission starting|mission success|mission completed)[,:] ?(.*)$", re.M)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eq(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    tab = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in tab["columns"]], [r for i in tab["instances"] for r in i["rows"]]


def validate_one(variant: str) -> dict:
    run = RUNS / RUN_IDS[variant]
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    eq(closure["error"], None, "closure error")
    eq(invocation["variant"], variant, "invocation variant")
    eq(invocation["session_id"], 0, "SSH session")
    eq(invocation["gui"]["pid"], 13340, "preserved GUI")
    eq(invocation["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "host mutex")
    eq(invocation["input_sha256"], SOURCES[variant], "input source")
    eq(sha(run / "invocation.json"), closure["invocation_sha256"], "invocation seal")
    eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    for name, path in {
        "input": HERE / f"{variant}-input.json",
        "parent": HERE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json",
        "contract": HERE / "contract.json",
        "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py",
        "runner_script": HERE / "run_native_ssh.ps1",
    }.items():
        eq(sha(path), closure["source_hashes_before"][name], f"source {name} seal")
    for name, info in closure["raw"].items():
        path = run / name
        eq(path.stat().st_size, info["bytes"], f"raw {name} size")
        eq(sha(path), info["sha256"], f"raw {name} seal")
    eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "step names")
    if any(s["status"] != "completed" or s["exit_code"] != 0 or s["gui_preserved"] is not True for s in steps):
        raise ValueError("native step failed or GUI was not preserved")
    roundtrip = check_roundtrip(run)
    if not roundtrip["passed"]:
        raise ValueError(f"source roundtrip differs: {roundtrip['differences']}")
    eq(len(roundtrip["populated_tables"]), 17, "source table count")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if not re.search(r"Input conversion completed\. Errors: 0, Warnings: 3, Notes: 0", calc):
        raise ValueError("conversion counts differ")
    eq(sorted(map(int, re.findall(r"warning #(\d+)", calc))), [108, 126, 126], "warning codes")
    if "Total execution time:" not in calc:
        raise ValueError("simulation completion marker absent")
    report = parse_native(run / "report-raw.json")
    summary_columns, summaries = rows(report, "ResultSummary")
    eq(len(summaries), 1, "summary count")
    summary = dict(zip(summary_columns, summaries[0]))
    for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1, "STMF": 1}.items():
        eq(summary[key], value, f"ResultSummary.{key}")
    columns, systems = rows(report, "SystemResults")
    eq(len(systems), 72, "system half-hour bins")
    eq(len(rows(report, "StockTotalResults")[1]), 72, "stock half-hour bins")
    idx = {k: columns.index(k) for k in ("STINT", "ETINT", "NSYRY", "NSYMO")}
    eq(systems[0][idx["NSYRY"]], 2 if variant == "b-missing" else 3, "initial ready aircraft")
    operating_hours = sum((r[idx["ETINT"]] - r[idx["STINT"]]) * r[idx["NSYMO"]] for r in systems)
    eq(operating_hours, 4.0, "aircraft mission hours")
    eq(systems[-1][idx["NSYRY"]], 2 if variant == "b-missing" else 3, "terminal ready aircraft")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    events: dict[str, list[tuple[float, str]]] = {}
    for match in EVENT.finditer(log):
        time, kind, detail = match.groups()
        events.setdefault(kind, []).append((float(time), detail))
    allocations = events.get("mission allocates system", [])
    eq([x[0] for x in allocations], [7.0, 7.0], "allocation times")
    eq([x[1] for x in allocations], EXPECTED_AIRCRAFT[variant], "allocated aircraft identities")
    for kind, time in (("mission starting", 8.0), ("mission success", 10.0), ("mission completed", 10.0)):
        eq(len(events.get(kind, [])), 1, f"{kind} count")
        eq(events[kind][0][0], time, f"{kind} time")
    if f"Active Formation {EXPECTED_FORMATION[variant]}:" not in events["mission starting"][0][1] or f"Active Formation {EXPECTED_FORMATION[variant]}:" not in events["mission completed"][0][1]:
        raise ValueError("active formation identifier differs")
    for aircraft in EXPECTED_AIRCRAFT[variant]:
        if aircraft not in events["mission starting"][0][1] or aircraft not in events["mission completed"][0][1]:
            raise ValueError(f"assigned {aircraft} missing from mission start/completion")
    return {"variant": variant, "run_id": RUN_IDS[variant], "closure_sha256": sha(run / "closure.json"), "source_tables": len(roundtrip["populated_tables"]), "allocated_aircraft": EXPECTED_AIRCRAFT[variant], "formation": EXPECTED_FORMATION[variant], "mission_start_hour": 8, "mission_complete_hour": 10, "aircraft_mission_hours": operating_hours, "system_bins": 72, "stock_bins": 72, "warnings": [108, 126, 126]}


def main() -> int:
    try:
        results = {variant: validate_one(variant) for variant in ("ab-high", "aa-high", "b-missing")}
        output = {"schema": "simlox-a11-explicit-formation-choice-v100-author-validation/v1", "passed": True, "scope": "two explicit formations with priority swap and unavailable-preferred fallback", "variants": results}
    except (OSError, KeyError, IndexError, StopIteration, TypeError, ValueError) as error:
        output = {"schema": "simlox-a11-explicit-formation-choice-v100-author-validation/v1", "passed": False, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(output, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
