"""Author replay of the frozen J07 success-point pair."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {
    "full-completion-control": "j07-full-success-control-v100-20261001-01",
    "early-success-point": "j07-early-success-v100-20261001-01",
}
checks = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name, condition, detail=None):
    checks.append({"name": name, "pass": bool(condition), "detail": detail})


def rows(report, name):
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for ins in table["instances"] for row in ins["rows"]]


def near(actual, expected, tol=1e-6):
    return actual is not None and math.isclose(float(actual), expected, abs_tol=tol, rel_tol=0)


contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
parent = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
ck("accepted_D06_fingerprint", sha(parent) == contract["input_sha256"]["full-completion-control"])
ck("exact_diff", set(diff["changed_tables"]) == {"MissionType", "ProblemDescription"}
   and diff["unchanged_table_count"] == 33
   and diff["parent_input_sha256"] == sha(parent)
   and diff["child_input_sha256"] == contract["input_sha256"]["early-success-point"])
reports = {}
logs = {}
for variant, run_id in RUNS.items():
    run = HERE / "runs" / run_id
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    source = HERE / f"{variant}-input.json"
    ck(f"{variant}_sealed_source", closure["run_id"] == invocation["run_id"] == run_id
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
       and len(before) == 18 and all(after[name] == table for name, table in before.items()))
    conversion = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{variant}_zero_conversion_errors", "Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in conversion)
    report = parse_native(run / "report-raw.json")
    reports[variant] = report
    ck(f"{variant}_report_shape", [t["name"] for t in report["report"]["tables"]]
       == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"])
    summary = rows(report, "ResultSummary")
    expected_msuf = 1/3 if variant == "full-completion-control" else 1
    ck(f"{variant}_summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and near(summary[0]["RTILW"], 0) and near(summary[0]["RTIUP"], 36)
       and all(near(summary[0][name], 1) for name in ("MTMF", "MSTF", "STMF"))
       and near(summary[0]["MSUF"], expected_msuf), summary)
    system = rows(report, "SystemResults")
    stock = rows(report, "StockTotalResults")
    ck(f"{variant}_bins", len(system) == len(stock) == 72
       and all(near(row["STINT"], i/2) and near(row["ETINT"], (i+1)/2)
               for series in (system, stock) for i, row in enumerate(series)))
    ck(f"{variant}_system_ledger", all(near(sum(float(row[field] or 0) for row in system) / 2, expected)
       for field, expected in (("NSYRY", 26), ("NSYMA", 9), ("NSYMO", 6),
                               ("NSYRP", 1), ("STACC", 6)))
       and sum(float(row["NFAIL"] or 0) for row in system) == 2
       and sum(float(row["NREPT"] or 0) for row in system) == 2)
    ck(f"{variant}_stock_ledger", all(row["PNB"] == 1 and all(
       value in (0, None) for field, value in row.items() if field not in ("STINT", "ETINT", "PNB"))
       for row in stock))
    ck(f"{variant}_terminal", near(system[-1]["NSYRY"], 1)
       and all(near(system[-1][field], 0) for field in ("NSYMA", "NSYMO", "NSYRP", "NFAIL")))
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    logs[variant] = log
    ck(f"{variant}_event_timeline", all(f"Time: {start} <BASIC-MISSION" in log
       for start in (8, 20, 32))
       and all(f"Time: {time} <BASIC-MISSION" in log and "mission aborted:" in log
               for time in ("9.8829", "33.8602"))
       and "Time: 22 <BASIC-MISSION" in log
       and len(re.findall(r"<BASIC-MISSION[^\n]*> mission starting,", log)) == 3
       and len(re.findall(r"<BASIC-MISSION[^\n]*> mission aborted:", log)) == 2
       and len(re.findall(r"<BASIC-MISSION[^\n]*> aborted mission completed:", log)) == 2)
    expected_successes = 1 if variant == "full-completion-control" else 3
    ck(f"{variant}_success_event_count", len(re.findall(
       r"<BASIC-MISSION[^\n]*> mission success:", log)) == expected_successes
       and all(f"Time: {time} <BASIC-MISSION" in log for time in (10, 22, 34)))

control = reports["full-completion-control"]
early = reports["early-success-point"]
ck("system_rows_identical", rows(control, "SystemResults") == rows(early, "SystemResults"))
ck("stock_rows_identical", rows(control, "StockTotalResults") == rows(early, "StockTotalResults"))
control_summary = rows(control, "ResultSummary")[0]
early_summary = rows(early, "ResultSummary")[0]
ck("only_summary_MSUF_changes", {k: v for k, v in control_summary.items() if k != "MSUF"}
   == {k: v for k, v in early_summary.items() if k != "MSUF"})
def strip_success(log):
    return [line.replace(", mission success,", ",") for line in log.splitlines()
            if not re.search(r"<BASIC-MISSION[^\n]*> mission success:", line)]
ck("same_non_success_event_lines", strip_success(logs["full-completion-control"])
   == strip_success(logs["early-success-point"]))
result = {"schema": "simlox-j07-success-point-author-validation/v1", "case_id": "J07",
          "version": "1.0.0", "run_ids": RUNS, "passed": all(x["pass"] for x in checks),
          "check_count": len(checks), "checks": checks,
          "scope": "MSUCPT_0.75_retrospectively_counts_aborted_missions_after_threshold"}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(f"{sum(x['pass'] for x in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
for item in checks:
    if not item["pass"]:
        print(item["name"], item["detail"])
raise SystemExit(0 if result["passed"] else 1)
