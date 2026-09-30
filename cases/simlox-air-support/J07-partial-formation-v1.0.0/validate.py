"""Author replay of the frozen J07 nominal-target versus minimum triplet."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {
    "full-control": "j07-full-form-control-v100-20261001-01",
    "strict-shortage": "j07-strict-shortage-v100-20261001-01",
    "partial-minimum": "j07-partial-minimum-v100-20261001-01",
}
EXPECTED = {
    "full-control": {"aircraft": 2, "ready": [(0, 7), (10, 36)], "assigned": [(7, 10)], "operating": [(8, 10)], "factors": (1, 1, 1, 1)},
    "strict-shortage": {"aircraft": 1, "ready": [(0, 7), (8 + 1/3, 36)], "assigned": [(7, 8 + 1/3)], "operating": [], "factors": (0, 0, 0, 0)},
    "partial-minimum": {"aircraft": 1, "ready": [(0, 7), (10, 36)], "assigned": [(7, 10)], "operating": [(8, 10)], "factors": (1, 1, 1, .5)},
}
checks = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name, condition, detail=None):
    checks.append({"name": name, "pass": bool(condition), "detail": detail})


def rows(report, name):
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for ins in table["instances"] for row in ins["rows"]]


def near(actual, expected, tol=1e-6):
    return actual is not None and math.isclose(float(actual), expected, abs_tol=tol, rel_tol=0)


def exposure(row, periods, aircraft):
    start, end = row["STINT"], row["ETINT"]
    return aircraft * sum(max(0.0, min(end, b) - max(start, a)) for a, b in periods) / (end - start)


contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
diff = json.loads((HERE / "exact-diffs.json").read_text(encoding="utf-8"))
parent = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
ck("accepted_A03_fingerprint", sha(parent) == contract["input_sha256"]["full-control"])
ck("exact_diff_parent", diff["parent_input_sha256"] == sha(parent)
   and set(diff["variants"]) == {"strict-shortage", "partial-minimum"})
for variant, changed in (("strict-shortage", {"SystemDeployment", "ProblemDescription"}),
                         ("partial-minimum", {"SystemDeployment", "ProblemDescription", "MissionType"})):
    item = diff["variants"][variant]
    ck(f"{variant}_exact_diff", set(item["changed_tables"]) == changed
       and item["unchanged_table_count"] == 31-len(changed)
       and item["child_input_sha256"] == contract["input_sha256"][variant])
reports = {}
logs = {}
for variant, run_id in RUNS.items():
    run = HERE / "runs" / run_id
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    source = HERE / f"{variant}-input.json"
    ck(f"{variant}_source_seal", closure["run_id"] == invocation["run_id"] == run_id
       and closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["input"] == sha(source) == contract["input_sha256"][variant]
       and closure["source_hashes_before"]["parent"] == sha(parent)
       and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
       and closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{variant}_raw_seals", all(sha(run / name) == info["sha256"]
       and (run / name).stat().st_size == info["bytes"] for name, info in closure["raw"].items()))
    ck(f"{variant}_five_steps", [s["name"] for s in steps]
       == ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    before = populated(parse_native(source))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    ck(f"{variant}_roundtrip", roundtrip["passed"] and not roundtrip["differences"]
       and len(before) == 13 and all(after[name] == table for name, table in before.items()))
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{variant}_zero_conversion_errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log)
    report = parse_native(run / "report-raw.json")
    reports[variant] = report
    ck(f"{variant}_report_shape", [t["name"] for t in report["report"]["tables"]]
       == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"])
    summary = rows(report, "ResultSummary")
    factors = EXPECTED[variant]["factors"]
    ck(f"{variant}_summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and near(summary[0]["RTILW"], 0) and near(summary[0]["RTIUP"], 36)
       and all(near(summary[0][key], expected) for key, expected in zip(
           ("MTMF", "MSTF", "MSUF", "STMF"), factors)), summary)
    system = rows(report, "SystemResults")
    stock = rows(report, "StockTotalResults")
    ck(f"{variant}_bins", len(system) == len(stock) == 72 and all(
       near(row["STINT"], i/2) and near(row["ETINT"], (i+1)/2)
       for series in (system, stock) for i, row in enumerate(series)))
    expected = EXPECTED[variant]
    ck(f"{variant}_system_ledger", all(
       near(row["NSYRY"], exposure(row, expected["ready"], expected["aircraft"]))
       and near(row["NSYMA"], exposure(row, expected["assigned"], expected["aircraft"]))
       and near(row["NSYMO"], exposure(row, expected["operating"], expected["aircraft"]))
       and near(row["STACC"], exposure(row, expected["operating"], expected["aircraft"]))
       and all(near(row[field], 0) for field in ("NFAIL", "NREPT", "NSYRP", "NSYPM"))
       for row in system))
    ck(f"{variant}_stock_ledger", all(row["PNB"] == 1 and all(
       value in (0, None) for field, value in row.items() if field not in ("STINT", "ETINT", "PNB"))
       for row in stock))
    ck(f"{variant}_terminal", near(system[-1]["NSYRY"], expected["aircraft"])
       and all(near(system[-1][field], 0) for field in ("NSYMA", "NSYMO", "NSYRP")))
    events = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    logs[variant] = events
    ck(f"{variant}_ordered_and_requested", "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION" in events
       and "mission activated, systems requested: 2" in events
       and len(re.findall(r"<BASIC-MISSION[^\n]*> mission allocates system:", events))
       == expected["aircraft"])
    starts = len(re.findall(r"<BASIC-MISSION[^\n]*> mission starting,", events))
    successes = len(re.findall(r"<BASIC-MISSION[^\n]*> mission success:", events))
    cancelled = len(re.findall(r"<BASIC-MISSION[^\n]*> mission cancelled:", events))
    if variant == "strict-shortage":
        ck("strict_cancellation", starts == successes == 0 and cancelled == 1
           and "mission waiting:  timeout at 8.33333" in events
           and "Time: 8.33333 <BASIC-MISSION" in events)
    else:
        ck(f"{variant}_wave_and_sorties", starts == successes == 1 and cancelled == 0
           and "Time: 8 <BASIC-MISSION" in events and "Time: 10 <BASIC-MISSION" in events
           and len(re.findall(r"<BASIC-MISSION[^\n]*> mission completed:", events)) == 1)

ck("partial_vs_full_mission_factors", all(near(rows(reports[v], "ResultSummary")[0][key], 1)
   for v in ("full-control", "partial-minimum") for key in ("MTMF", "MSTF", "MSUF")))
ck("partial_nominal_system_denominator", near(rows(reports["partial-minimum"], "ResultSummary")[0]["STMF"], 2/4))
result = {"schema": "simlox-j07-partial-formation-author-validation/v1", "case_id": "J07",
          "version": "1.0.0", "run_ids": RUNS, "passed": all(x["pass"] for x in checks),
          "check_count": len(checks), "checks": checks,
          "scope": "one_nominal_two_aircraft_wave_with_one_available_and_MNOS_one"}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"{sum(x['pass'] for x in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
for item in checks:
    if not item["pass"]:
        print(item["name"], item["detail"])
raise SystemExit(0 if result["passed"] else 1)
