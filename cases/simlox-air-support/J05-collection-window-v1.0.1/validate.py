"""Author replay of the frozen J05 collection-window native triplet."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
RUNS = {
    "baseline": ("j05-baseline-v101-20261001-01", 0.0, 36.0, 0.5, 13),
    "global-window": ("j05-global-window-v101-20261001-01", 7.5, 9.0, 0.25, 12),
    "system-override": ("j05-system-override-v101-20261001-01", 0.0, 36.0, 0.5, 13),
}
checks: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ck(name: str, condition: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(condition), "detail": detail})


def records(report: dict, name: str) -> list[dict]:
    table = next(t for t in report["report"]["tables"] if t["name"] == name)
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


def close(a: object, b: float) -> bool:
    return a is not None and abs(float(a) - b) < 1e-9


contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
ck("contract_before_native", contract["version"] == "1.0.1-candidate")
reports = {}
logs = {}
for variant, (run_id, start, end, interval, source_tables) in RUNS.items():
    run = HERE / "runs" / run_id
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    raw = closure["raw"]
    ck(f"{variant}_identity", closure["run_id"] == run_id and invocation["run_id"] == run_id)
    ck(f"{variant}_source_seal", closure["source_hashes_before"] == closure["source_hashes_after"]
       and closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
       and closure["source_hashes_before"]["input"] == contract["input_sha256"][variant])
    ck(f"{variant}_invocation_seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck(f"{variant}_raw_seals", all(sha(run / name) == value["sha256"]
       and (run / name).stat().st_size == value["bytes"] for name, value in raw.items()), len(raw))
    ck(f"{variant}_roundtrip", json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))["passed"]
       and populated(parse_native(run / "input.json")) ==
       {name: table for name, table in populated(parse_native(run / "roundtrip-raw.json")).items()
        if name in populated(parse_native(run / "input.json"))}
       and len(populated(parse_native(run / "input.json"))) == source_tables)
    step_names = [step["name"] for step in steps]
    ck(f"{variant}_five_steps", step_names == ["import", "export", "calc", "jsonreport", "check_import_export"]
       and all(step.get("exit_code") == 0 for step in steps), step_names)
    conversion_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck(f"{variant}_zero_conversion_errors", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conversion_log)
    logs[variant] = (run / "model.log").read_bytes()
    report = parse_native(run / "report-raw.json")
    reports[variant] = report
    names = [t["name"] for t in report["report"]["tables"]]
    ck(f"{variant}_report_tables", names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"], names)
    summary = records(report, "ResultSummary")
    ck(f"{variant}_full_run_summary", len(summary) == 1 and summary[0]["NREP"] == 1
       and summary[0]["RTILW"] == 0 and summary[0]["RTIUP"] == 36
       and summary[0]["MTMF"] == summary[0]["MSTF"] == summary[0]["MSUF"] == summary[0]["STMF"] == 1)
    system = records(report, "SystemResults")
    stock = records(report, "StockTotalResults")
    stock_start, stock_end, stock_interval = (7.5, 9.0, 0.25) if variant == "system-override" else (start, end, interval)
    ck(f"{variant}_system_bins", len(system) == round((end - start) / interval)
       and all(close(row["STINT"], start + i * interval) and close(row["ETINT"], start + (i + 1) * interval)
               for i, row in enumerate(system)), len(system))
    ck(f"{variant}_stock_bins", len(stock) == round((stock_end - stock_start) / stock_interval)
       and all(close(row["STINT"], stock_start + i * stock_interval)
               and close(row["ETINT"], stock_start + (i + 1) * stock_interval)
               for i, row in enumerate(stock)), len(stock))
    ck(f"{variant}_event_derived_states", all(
       close(row["NSYRY"], 1.0 if row["ETINT"] <= 7 or row["STINT"] >= 10 else 0.0)
       and close(row["NSYMA"], 1.0 if row["STINT"] >= 7 and row["ETINT"] <= 10 else 0.0)
       and close(row["NSYMO"], 1.0 if row["STINT"] >= 8 and row["ETINT"] <= 10 else 0.0)
       and close(row["STACC"], 1.0 if row["STINT"] >= 8 and row["ETINT"] <= 10 else 0.0)
       for row in system))
    ck(f"{variant}_no_stock_events", all(row["PNB"] == 1 and all(value in (0, None)
       for key, value in row.items() if key not in ("STINT", "ETINT", "PNB")) for row in stock))

ck("identical_full_event_log", len(set(logs.values())) == 1
   and b"Time: 8 <BASIC-MISSION" in logs["baseline"]
   and b"Time: 10 <BASIC-MISSION" in logs["baseline"]
   and b"mission success" in logs["baseline"]
   and b"Time: 24  Start of day no 1" in logs["baseline"])
ck("system_override_equals_baseline", records(reports["baseline"], "SystemResults") ==
   records(reports["system-override"], "SystemResults"))
ck("stock_override_equals_global", records(reports["global-window"], "StockTotalResults") ==
   records(reports["system-override"], "StockTotalResults"))
ck("summary_same_all", records(reports["baseline"], "ResultSummary") ==
   records(reports["global-window"], "ResultSummary") ==
   records(reports["system-override"], "ResultSummary"))
result = {
    "schema": "simlox-j05-window-author-validation/v1",
    "case_id": "J05", "version": "1.0.1", "run_ids": [x[0] for x in RUNS.values()],
    "passed": all(x["pass"] for x in checks), "check_count": len(checks), "checks": checks,
    "scope": "global_control_window_and_system_result_type_override_relative_to_stock_total",
    "mission_interval_status": "not_directly_exposed_in_jsonreport",
}
out = HERE / "review" / "author-validation-2026-10-01.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{sum(x['pass'] for x in checks)}/{len(checks)} author checks: {'PASS' if result['passed'] else 'FAIL'}")
if not result["passed"]:
    for item in checks:
        if not item["pass"]:
            print(item["name"], item["detail"])
raise SystemExit(0 if result["passed"] else 1)
