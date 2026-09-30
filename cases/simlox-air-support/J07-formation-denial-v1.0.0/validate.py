"""Author replay of the frozen J07 native triplet; reads sealed raw runs only."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {
    "single-control": "j07-single-control-v100-20261001-01",
    "formation-control": "j07-formation-control-v100-20261001-01",
    "denied-demand": "j07-denied-demand-v100-20261001-01",
}
EXPECTED = {
    "single-control": (1, 1, 1, 1, 1),
    "formation-control": (1, 1, 1, 1, 2),
    "denied-demand": (0.5, 0.5, 0.5, 0.4, 2),
}
checks = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name, ok, detail=None):
    checks.append({"name": name, "pass": bool(ok), "detail": detail})


def rows(report, name):
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for ins in table["instances"] for row in ins["rows"]]


def near(actual, expected, tol=1e-6):
    return actual is not None and math.isclose(float(actual), expected, abs_tol=tol, rel_tol=0)


def overlap(start, end, low, high):
    return max(0.0, min(end, high) - max(start, low))


contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
ck("frozen_contract", contract["version"] == "1.0.0-candidate")
logs = {}
for variant, run_id in RUNS.items():
    run = HERE / "runs" / run_id
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    source = HERE / f"{variant}-input.json"
    ck(f"{variant}_source_and_invocation", closure["run_id"] == invocation["run_id"] == run_id
       and closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["input"] == sha(source) == contract["input_sha256"][variant]
       and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
       and closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{variant}_raw_seals", all(sha(run / name) == info["sha256"]
       and (run / name).stat().st_size == info["bytes"] for name, info in closure["raw"].items()),
       len(closure["raw"]))
    ck(f"{variant}_five_native_steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    original = populated(parse_native(source))
    exported = populated(parse_native(run / "roundtrip-raw.json"))
    ck(f"{variant}_source_roundtrip", roundtrip["passed"] and not roundtrip["differences"]
       and len(original) == 13 and all(exported[name] == table for name, table in original.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{variant}_zero_conversion_errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conversion)
    report = parse_native(run / "report-raw.json")
    names = [t["name"] for t in report["report"]["tables"]]
    ck(f"{variant}_report_shape", names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"])
    summary = rows(report, "ResultSummary")
    mtmf, mstf, msuf, stmf, aircraft = EXPECTED[variant]
    ck(f"{variant}_summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and near(summary[0]["RTILW"], 0) and near(summary[0]["RTIUP"], 36)
       and all(near(summary[0][field], target) for field, target in
               (("MTMF", mtmf), ("MSTF", mstf), ("MSUF", msuf), ("STMF", stmf))), summary)
    system = rows(report, "SystemResults")
    stock = rows(report, "StockTotalResults")
    ck(f"{variant}_bins", len(system) == len(stock) == 72 and all(
       near(r["STINT"], i / 2) and near(r["ETINT"], (i + 1) / 2)
       for series in (system, stock) for i, r in enumerate(series)))
    ck(f"{variant}_stock_ledger", all(r["PNB"] == 1 and all(
       value in (0, None) for key, value in r.items() if key not in ("STINT", "ETINT", "PNB"))
       for r in stock))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    logs[variant] = log
    ck(f"{variant}_first_wave", len(re.findall(r"mission starting, duration: 2", log)) == 1
       and "Time: 8 <BASIC-MISSION" in log and "Time: 10 <BASIC-MISSION" in log
       and len(re.findall(r"<BASIC-MISSION[^\n]*> mission success:", log)) == 1
       and len(re.findall(r"<BASIC-MISSION[^\n]*> mission completed:", log)) == 1
       and log.count("task starting:") == log.count("task completed:") == 1)
    ck(f"{variant}_formation_aircraft", len(re.findall(
       r"<BASIC-MISSION[^\n]*> mission allocates system:", log)) == aircraft)
    if variant == "denied-demand":
        ck("denied_event_ledger", "Time: 11 <TEACH-UNIT> mission ordered: THREE-AIR-DEMAND" in log
           and "mission activated, systems requested: 3" in log
           and "mission waiting:  timeout at 12.3333" in log
           and "Time: 12.3333 <THREE-AIR-DEMAND" in log
           and log.count("mission cancelled:") == 1
           and "<THREE-AIR-DEMAND" in log
           and not re.search(r"<THREE-AIR-DEMAND[^\n]*> mission (starting|success|completed):", log)
           and len(re.findall(r"<THREE-AIR-DEMAND[^\n]*> mission allocates system:", log)) == 2)
        ready = [(0, 7), (10, 11), (12 + 1/3, 36)]
        assigned = [(7, 10), (11, 12 + 1/3)]
    else:
        ck(f"{variant}_no_extra_demand", "THREE-AIR-DEMAND" not in log and "mission cancelled:" not in log)
        ready = [(0, 7), (10, 36)]
        assigned = [(7, 10)]
    ck(f"{variant}_system_state_ledger", all(
       near(r["NSYRY"], aircraft * sum(overlap(r["STINT"], r["ETINT"], a, b) for a, b in ready) / 0.5)
       and near(r["NSYMA"], aircraft * sum(overlap(r["STINT"], r["ETINT"], a, b) for a, b in assigned) / 0.5)
       and near(r["NSYMO"], aircraft * overlap(r["STINT"], r["ETINT"], 8, 10) / 0.5)
       and near(r["STACC"], aircraft * overlap(r["STINT"], r["ETINT"], 8, 10) / 0.5)
       for r in system))
    ck(f"{variant}_terminal", near(system[-1]["NSYRY"], aircraft)
       and near(system[-1]["NSYMA"], 0) and near(system[-1]["NSYMO"], 0)
       and all(near(system[-1][field], 0) for field in ("NFAIL", "NPMT", "NSYWR", "NSYWI"))
       and f"systems ready: {aircraft} :" in log and "Time: 24  Start of day no 1" in log)

ck("formation_control_equals_denied_first_wave", all(
    line in logs["denied-demand"] for line in logs["formation-control"].splitlines()
    if line.startswith("Time: ") and ("BASIC-MISSION" in line or line.startswith("Time: 24"))))
result = {"schema": "simlox-j07-author-validation/v1", "case_id": "J07", "version": "1.0.0",
          "run_ids": RUNS, "passed": all(c["pass"] for c in checks),
          "check_count": len(checks), "checks": checks,
          "scope": "single_and_formation_controls_plus_cancelled_three_aircraft_fixed_demand"}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"{sum(c['pass'] for c in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
for check in checks:
    if not check["pass"]:
        print(check["name"], check["detail"])
raise SystemExit(0 if result["passed"] else 1)
