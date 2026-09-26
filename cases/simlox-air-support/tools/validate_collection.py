"""Describe collection-window probes without imposing the normal A01 outcome."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from build_horizon_variants import ENDS, SOURCE
from validate_native import compare_roundtrip, parse_log, remove_trailing_commas, table_rows


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clipped_flight_hours(start: float | None, completion: float | None, window_end: float) -> float:
    if start is None or window_end <= start:
        return 0.0
    return max(0.0, min(window_end, completion if completion is not None else window_end) - start)


def rows(model: dict, name: str) -> list[dict]:
    table = next(t for t in model["model"]["tables"] if t["name"] == name)
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


def validate(run: Path, variant: str, *, write: bool = True) -> dict:
    required = ["input.json", "model.sxi", "model.sxo", "roundtrip-raw.json",
                "report-raw.json", "run.log", "model.log", "steps.json"]
    for name in required:
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            raise ValueError(f"missing/invalid native artifact: {name}")
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    if [step["name"] for step in steps] != ["import", "export", "calc", "jsonreport"] or any(step["exit_code"] != 0 for step in steps):
        raise ValueError("native command sequence invalid")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    input_model = json.loads((run / "input.json").read_text(encoding="utf-8"))
    changed = []
    for table in source["model"]["tables"]:
        original, actual = rows(source, table["name"]), rows(input_model, table["name"])
        for index, (before, after) in enumerate(zip(original, actual)):
            for column in before:
                if before[column] != after[column]:
                    changed.append(f"{table['name']}[{index}].{column}")
        if len(original) != len(actual):
            raise ValueError(f"row count changed in {table['name']}")
    allowed = {"Control[0].RCEND",
               "ResultCollection[0].RCEND", "ResultCollection[1].RCEND"}
    if set(changed) != allowed:
        raise ValueError(f"unexpected input changes: {changed}")
    end = ENDS[variant]
    if any(row[field] != end for table, field in (("Control", "RCEND"),
                                                  ("ResultCollection", "RCEND")) for row in rows(input_model, table)):
        raise ValueError("observation end does not match variant")
    if rows(input_model, "Control")[0]["SIMPE"] != 36:
        raise ValueError("simulation period must remain the accepted 36 h")
    roundtrip = compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
    if not roundtrip["all_equal"] or roundtrip["nonempty_business_tables"] < 1:
        raise ValueError("native business rows changed")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    match = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    if not match or int(match[1]) != 0:
        raise ValueError("native conversion errors/missing summary")
    warnings = re.findall(r"\(warning #(\d+)\) ([^\r\n]+)", run_log)
    if len(warnings) != int(match[2]) or {item[0] for item in warnings} - {"108", "126"}:
        raise ValueError("unexplained native warning")
    normalized = remove_trailing_commas((run / "report-raw.json").read_bytes())
    report = json.loads(normalized)
    summary = table_rows(report, "ResultSummary")
    system = table_rows(report, "SystemResults")
    events = parse_log(run / "model.log")
    if not events or len(summary) != 1:
        raise ValueError("no parsed events or no ResultSummary")
    by_kind = {kind: [event for event in events if event["kind"] == kind]
               for kind in ("notification", "start", "completion", "success", "cancel", "abort", "ready_increased")}
    if len(by_kind["notification"]) != 1 or float(by_kind["notification"][0]["time_hours_printed"]) != 7:
        raise ValueError("A01 notification missing/mismatched")
    starts = [float(event["time_hours_printed"]) for event in by_kind["start"]]
    completes = [float(event["time_hours_printed"]) for event in by_kind["completion"]]
    if len(starts) > 1 or len(completes) > 1 or (completes and not starts):
        raise ValueError("unexpected duplicate/unpaired mission events")
    clip = clipped_flight_hours(starts[0] if starts else None, completes[0] if completes else None, end)
    ftmo = sum(float(row["FTMO"]) * (float(row["ETINT"]) - float(row["STINT"])) for row in system)
    observed = {"requested_observation_end_hours": end,
                "native_summary_window_hours": [summary[0]["RTILW"], summary[0]["RTIUP"]],
                "native_summary_mstf_msuf": [summary[0]["MSTF"], summary[0]["MSUF"]],
                "native_system_result_interval_count": len(system),
                "native_system_result_last_end_hours": system[-1]["ETINT"] if system else None,
                "starts_hours_printed": starts, "completions_hours_printed": completes,
                "success_hours_printed": [e["time_hours_printed"] for e in by_kind["success"]],
                "cancel_hours_printed": [e["time_hours_printed"] for e in by_kind["cancel"]],
                "abort_hours_printed": [e["time_hours_printed"] for e in by_kind["abort"]],
                "flight_hours_clipped_from_events": clip,
                "native_ftmo_interval_integral_hours": ftmo,
                "planned_unlaunched_at_collection_end": int(bool(starts) and starts[0] > end),
                "in_flight_at_collection_end": int(bool(starts) and starts[0] <= end and (not completes or completes[0] > end)),
                "completed_by_collection_end": int(bool(completes) and completes[0] <= end),
                "completion_after_requested_end": bool(completes and completes[0] > end),
                "selected_events": [e for e in events if e["kind"] in {"notification", "start", "completion", "success", "cancel", "abort", "ready_increased"}]}
    result = {"variant": variant, "status": "native_probe_recorded", "changed_fields": changed,
              "input_sha256": sha(run / "input.json"),
              "raw_report_sha256": sha(run / "report-raw.json"),
              "normalized_report_sha256": hashlib.sha256(normalized).hexdigest(),
              "sxi_sha256": sha(run / "model.sxi"), "sxo_sha256": sha(run / "model.sxo"),
              "enlog_sha256": sha(run / "model.log"),
              "roundtrip": roundtrip,
              "conversion": {"errors": int(match[1]), "warnings": int(match[2]), "details": warnings},
              "observation": observed}
    if write:
        for name, contents in (("report-normalized.json", normalized),
                               ("validation.json", (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))):
            path = run / name
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(contents)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--variant", choices=sorted(ENDS), required=True)
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    result = validate(args.run_dir, args.variant, write=not args.read_only)
    print(json.dumps({"variant": args.variant, "status": result["status"],
                      "observation": result["observation"]}))


if __name__ == "__main__":
    main()
