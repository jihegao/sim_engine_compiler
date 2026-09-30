"""Source-bound author replay of A10 default-profile native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
RUN_IDS = {"48h": "a10-default-48h-20260930-01", "50h": "a10-default-50h-20260930-01"}
SOURCES = {"48h": "3362c767cc64cf58b7ec6c2de59cc865a122626cf3c67f16772c4baa35fe246a", "50h": "a8cc2d4933df9e873b19061dc853a9862b9627b88624684f62cb699d73334a1e"}
PARAMETERS = {"48h": (48.0, 3.0, 4.5), "50h": (50.0, 3.125, 4.4375)}
MISSION = "<TEACH-UNIT_TEACH-AIR-01_MISSION>"
AIRCRAFT = "<TEACH-AIR-01,0>"
EVENT = re.compile(r"^Time: ([0-9.]+) <(<TEACH-UNIT_TEACH-AIR-01_MISSION>,TEACH-UNIT,0,0,([0-3]))> (mission created|mission activated|mission allocates system|mission starting|mission success|mission completed)[,:] ?(.*)$", re.M)


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
    horizon, duration, first = PARAMETERS[variant]
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    eq(closure["error"], None, "closure error")
    eq(invocation["variant"], variant, "invocation variant")
    eq(invocation["session_id"], 0, "SSH session")
    eq(invocation["gui"]["pid"], 13340, "preserved GUI")
    eq(invocation["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "host mutex")
    eq(invocation["input_sha256"], SOURCES[variant], "input fingerprint")
    eq(sha(run / "invocation.json"), closure["invocation_sha256"], "invocation seal")
    eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    for key, path in {
        "input": HERE / f"{variant}-input.json",
        "parent": HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json",
        "contract": HERE / "contract.json",
        "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py",
        "runner_script": HERE / "run_native_ssh.ps1",
    }.items():
        eq(sha(path), closure["source_hashes_before"][key], f"{key} source seal")
    for filename, info in closure["raw"].items():
        path = run / filename
        eq(path.stat().st_size, info["bytes"], f"{filename} byte count")
        eq(sha(path), info["sha256"], f"{filename} raw seal")
    eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "step names")
    if any(s["status"] != "completed" or s["exit_code"] != 0 or s["gui_preserved"] is not True for s in steps):
        raise ValueError("native step failed or GUI changed")
    roundtrip = check_roundtrip(run)
    if not roundtrip["passed"]:
        raise ValueError(f"source roundtrip differs: {roundtrip['differences']}")
    eq(len(roundtrip["populated_tables"]), 11, "source populated table count")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0, Warnings: 2, Notes: 4" not in calc:
        raise ValueError("conversion result differs")
    eq(sorted(map(int, re.findall(r"warning #(\d+)", calc))), [108, 126], "warning codes")
    if "Total execution time:" not in calc:
        raise ValueError("simulation completion marker absent")
    report = parse_native(run / "report-raw.json")
    sc, sr = rows(report, "ResultSummary")
    eq(len(sr), 1, "summary row count")
    summary = dict(zip(sc, sr[0]))
    for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": horizon, "MTMF": 1, "MSTF": 0, "MSUF": 0, "STMF": 1}.items():
        eq(summary[key], value, f"ResultSummary.{key}")
    columns, systems = rows(report, "SystemResults")
    stock_columns, stocks = rows(report, "StockTotalResults")
    eq(len(systems), int(horizon * 2), "half-hour system bins")
    eq(len(stocks), int(horizon * 2), "half-hour stock bins")
    ci = {name: columns.index(name) for name in ("STINT", "ETINT", "NSYRY", "NSYMO", "FTMO", "NSYA", "NFAIL", "NPMT", "NPMS")}
    eq(systems[0][ci["STINT"]], 0, "system initial time")
    eq(systems[-1][ci["ETINT"]], horizon, "system terminal time")
    eq(systems[0][ci["NSYRY"]], 1, "initial ready aircraft")
    eq(systems[-1][ci["NSYRY"]], 1, "terminal ready aircraft")
    eq(systems[-1][ci["NSYA"]], 1, "terminal available aircraft")
    if any(r[ci["NFAIL"]] or r[ci["NPMT"]] or r[ci["NPMS"]] for r in systems):
        raise ValueError("unexpected failure or preventive maintenance")
    mission_hours = sum((r[ci["ETINT"]] - r[ci["STINT"]]) * r[ci["NSYMO"]] for r in systems)
    ftmo_hours = sum((r[ci["ETINT"]] - r[ci["STINT"]]) * r[ci["FTMO"]] for r in systems)
    eq(round(mission_hours, 9), 4 * duration, "mission aircraft-hours")
    eq(round(ftmo_hours, 9), 4 * duration, "FTMO aircraft-hours")
    si = {name: stock_columns.index(name) for name in ("STINT", "ETINT", "NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")}
    eq(stocks[0][si["STINT"]], 0, "stock initial time")
    eq(stocks[-1][si["ETINT"]], horizon, "stock terminal time")
    if any(r[si[k]] for r in stocks for k in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")):
        raise ValueError("unexpected stock demand, movement or waiting")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    events: dict[str, list[tuple[float, int, str]]] = {}
    for match in EVENT.finditer(log):
        time, _, wave, kind, detail = match.groups()
        events.setdefault(kind, []).append((float(time), int(wave), detail))
    for kind in ("mission created", "mission activated", "mission allocates system", "mission starting", "mission success", "mission completed"):
        eq(len(events.get(kind, [])), 4, f"{kind} event count")
        eq([wave for _, wave, _ in events[kind]], [0, 1, 2, 3], f"{kind} wave identities")
    starts = [first + 12 * i for i in range(4)]
    ends = [time + duration for time in starts]
    eq([x[0] for x in events["mission starting"]], starts, "implicit mission start times")
    eq([x[0] for x in events["mission completed"]], ends, "implicit mission completion times")
    eq([x[0] for x in events["mission success"]], ends, "implicit mission success times")
    eq([x[0] for x in events["mission allocates system"]], starts, "individual allocation times")
    if any(AIRCRAFT not in detail for _, _, detail in events["mission allocates system"] + events["mission starting"] + events["mission completed"]):
        raise ValueError("implicit mission aircraft identity differs")
    if any(f"duration: {duration:g}" not in detail for _, _, detail in events["mission starting"]):
        raise ValueError("implicit mission duration differs")
    if "BASIC-MISSION" in log or "BASIC-SCHEDULE" in log:
        raise ValueError("explicit parent mission/profile appeared in native log")
    return {"variant": variant, "run_id": RUN_IDS[variant], "closure_sha256": sha(run / "closure.json"), "source_tables": 11, "generated_mission": MISSION, "starts": starts, "completions": ends, "duration_hours": duration, "aircraft_mission_hours": mission_hours, "system_bins": len(systems), "stock_bins": len(stocks), "warnings": [108, 126], "conversion_notes": 4}


def main() -> int:
    try:
        variants = {v: one(v) for v in RUN_IDS}
        result = {"schema": "simlox-a10-default-profile-horizon-v100-author-validation/v1", "passed": True, "variants": variants}
    except (OSError, KeyError, IndexError, StopIteration, TypeError, ValueError) as exc:
        result = {"schema": "simlox-a10-default-profile-horizon-v100-author-validation/v1", "passed": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
