"""Source-bound author replay of B04 cross-midnight turnround pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
RUN_IDS = {"control": "b04-v101-control-20260930-01", "turnround": "b04-v101-turnround-20260930-01"}
SOURCES = {"control": "9cc5c39a6d2d93b98c03fc0c483bf90963a76e67be6953444003f30bfa8dd98c", "turnround": "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"}
AIRCRAFT = "<TEACH-AIR-01,0>"
MISSION = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,([01])> (mission allocates system|mission preassigns a system|mission starting|mission success|mission completed|mission cancelled)[,:] ?(.*)$", re.M)
PERSON = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> (preparation started|preparation ended|turnround started|turnround ended), mission: <BASIC-MISSION,TEACH-UNIT,0,0,([01])>", re.M)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eq(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: expected {expected!r}, got {actual!r}")


def rows(report: dict, name: str) -> tuple[list[str], list[list]]:
    tab = next(t for t in report["report"]["tables"] if t["name"] == name)
    return [c["name"] for c in tab["columns"]], [r for i in tab["instances"] for r in i["rows"]]


def one(variant: str) -> dict:
    run = HERE / "runs" / RUN_IDS[variant]
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    eq(closure["error"], None, "closure error")
    eq(invocation["variant"], variant, "variant")
    eq(invocation["session_id"], 0, "SSH session")
    eq(invocation["gui"]["pid"], 13340, "GUI identity")
    eq(invocation["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "host mutex")
    eq(invocation["input_sha256"], SOURCES[variant], "input fingerprint")
    eq(sha(run / "invocation.json"), closure["invocation_sha256"], "invocation seal")
    eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    for key, path in {
        "input": HERE / f"{variant}-input.json",
        "parent": HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json",
        "contract": HERE / "contract.json",
        "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py",
        "runner_script": HERE / "run_native_ssh.ps1",
    }.items():
        eq(sha(path), closure["source_hashes_before"][key], f"source seal {key}")
    for filename, info in closure["raw"].items():
        path = run / filename
        eq(path.stat().st_size, info["bytes"], f"raw bytes {filename}")
        eq(sha(path), info["sha256"], f"raw SHA {filename}")
    eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "steps")
    if any(s["status"] != "completed" or s["exit_code"] != 0 or s["gui_preserved"] is not True for s in steps):
        raise ValueError("native step failed or GUI changed")
    rt = check_roundtrip(run)
    if not rt["passed"]:
        raise ValueError(f"roundtrip differences: {rt['differences']}")
    eq(len(rt["populated_tables"]), 17 if variant == "control" else 18, "populated source tables")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" not in calc:
        raise ValueError("conversion result differs")
    eq(sorted(map(int, re.findall(r"warning #(\d+)", calc))), [108, 126], "warning codes")
    if "Total execution time:" not in calc:
        raise ValueError("simulation completion marker absent")
    report = parse_native(run / "report-raw.json")
    sc, sr = rows(report, "ResultSummary")
    eq(len(sr), 1, "summary rows")
    summary = dict(zip(sc, sr[0]))
    for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1, "MSTF": 1, "MSUF": 1, "STMF": 1}.items():
        eq(summary[key], value, f"ResultSummary.{key}")
    c, systems = rows(report, "SystemResults")
    stock_c, stocks = rows(report, "StockTotalResults")
    eq(len(systems), 72, "system bins")
    eq(len(stocks), 72, "stock bins")
    ix = {x: c.index(x) for x in ("STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMT", "NSYMP", "FTMO", "NFAIL", "NPMS", "NPMT")}
    eq(systems[0][ix["STINT"]], 0, "system initial time")
    eq(systems[-1][ix["ETINT"]], 36, "system terminal time")
    eq(systems[0][ix["NSYRY"]], 1, "initial ready")
    eq(systems[-1][ix["NSYRY"]], 1, "terminal ready")
    for row in systems:
        if abs(row[ix["NSYRY"]] + row[ix["NSYMA"]] - 1) > 1e-9:
            raise ValueError("one-aircraft ready/assigned ledger differs")
        if any(row[ix[k]] for k in ("NFAIL", "NPMS", "NPMT")):
            raise ValueError("unexpected failure or PM")
    def integral(field: str) -> float:
        return sum((r[ix["ETINT"]] - r[ix["STINT"]]) * (r[ix[field]] or 0) for r in systems)
    eq(integral("NSYMO"), 4.0, "four aircraft mission-hours")
    eq(integral("FTMO"), 4.0, "FTMO hours")
    eq(integral("NSYMP"), 1.0, "serial preparation hours")
    eq(integral("NSYMT"), 0.0 if variant == "control" else 2.0, "turnround hours")
    sx = {x: stock_c.index(x) for x in ("STINT", "ETINT", "NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")}
    eq(stocks[0][sx["STINT"]], 0, "stock initial time")
    eq(stocks[-1][sx["ETINT"]], 36, "stock terminal time")
    if any(r[sx[k]] for r in stocks for k in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")):
        raise ValueError("unexpected stock demand, movement or wait")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    events: dict[tuple[int, str], list[tuple[float, str]]] = {}
    for match in MISSION.finditer(log):
        time, wave, kind, detail = match.groups()
        events.setdefault((int(wave), kind), []).append((float(time), detail))
    personal: dict[tuple[int, str], list[float]] = {}
    for match in PERSON.finditer(log):
        time, kind, wave = match.groups()
        personal.setdefault((int(wave), kind), []).append(float(time))
    expected = {
        (0, "mission allocates system"): 20.5,
        (0, "mission starting"): 21.5,
        (0, "mission success"): 23.5,
        (0, "mission completed"): 23.5,
        (1, "mission allocates system"): 23.75 if variant == "control" else 24.5,
        (1, "mission starting"): 24.75 if variant == "control" else 25.0,
        (1, "mission success"): 26.75 if variant == "control" else 27.0,
        (1, "mission completed"): 26.75 if variant == "control" else 27.0,
    }
    eq(set(events) - {(1, "mission preassigns a system")}, set(expected), "mission event kinds")
    for key, time in expected.items():
        eq(len(events[key]), 1, f"{key} count")
        eq(events[key][0][0], time, f"{key} time")
        if key[1] in ("mission allocates system", "mission starting", "mission completed") and AIRCRAFT not in events[key][0][1]:
            raise ValueError(f"{key} aircraft identity absent")
    eq(events.get((1, "mission preassigns a system"), []), [] if variant == "control" else [(23.75, AIRCRAFT)], "next-wave preassignment")
    person_expected = {
        (0, "preparation started"): 20.5, (0, "preparation ended"): 21.0,
        (0, "turnround started"): 23.5,
        (0, "turnround ended"): 23.5 if variant == "control" else 24.5,
        (1, "preparation started"): 23.75 if variant == "control" else 24.5,
        (1, "preparation ended"): 24.25 if variant == "control" else 25.0,
        (1, "turnround started"): 26.75 if variant == "control" else 27.0,
        (1, "turnround ended"): 26.75 if variant == "control" else 28.0,
    }
    eq(personal, {key: [time] for key, time in person_expected.items()}, "preparation/turnround lifecycle")
    if "mission cancelled" in log or "mission aborted" in log:
        raise ValueError("unexpected cancellation or abort")
    return {"variant": variant, "run_id": RUN_IDS[variant], "closure_sha256": sha(run / "closure.json"), "source_tables": len(rt["populated_tables"]), "second_start_hour": expected[(1, "mission starting")], "second_complete_hour": expected[(1, "mission completed")], "turnround_hours": integral("NSYMT"), "preparation_hours": integral("NSYMP"), "mission_hours": integral("NSYMO"), "system_bins": 72, "stock_bins": 72, "warnings": [108, 126]}


def main() -> int:
    try:
        result = {"schema": "simlox-b04-cross-midnight-turnround-v101-author-validation/v1", "passed": True, "variants": {v: one(v) for v in RUN_IDS}}
    except (OSError, KeyError, IndexError, StopIteration, TypeError, ValueError) as exc:
        result = {"schema": "simlox-b04-cross-midnight-turnround-v101-author-validation/v1", "passed": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
