#!/usr/bin/env python3
"""Verify and summarize a frozen three-arm evidence directory without timing it."""
import argparse
import json
import math
from pathlib import Path
from statistics import median
from typing import Any

try:
    from benchmarks.three_arm_v1 import driver
except ModuleNotFoundError:  # Support direct execution from this directory.
    import driver  # type: ignore[no-redef]


ARMS = ("scan", "cache", "candidates")
COMPARISONS = (("cache", "scan"), ("candidates", "scan"), ("candidates", "cache"))
RATIO_KEYS = ("execution", "end_to_end", "rss")


def _positive_number(value: Any, label: str) -> int | float:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return value


def _regression_measures(ratios: dict[str, float]) -> list[str]:
    measures = []
    if ratios["execution"] >= 1.05:
        measures.append("execution")
    if ratios["end_to_end"] >= 1.05:
        measures.append("end_to_end")
    if ratios["rss"] > 1.05:
        measures.append("rss")
    return measures


def _load_complete_cell(
    directory: Path,
    manifest: dict[str, Any],
    cell: dict[str, Any],
    record_path: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    cell_label = f"cell-{cell['ordinal']:03d}"
    report_path = record_path.parent / "stage-c-report.json"
    if not report_path.is_file():
        raise ValueError(f"{cell_label} complete record is missing stage-c-report.json")
    report_sha256 = driver.sha256_file(report_path)
    if record.get("stage_c_report_sha256") != report_sha256:
        raise ValueError(f"{cell_label} stage-c report hash mismatch")
    report = driver._load_object(report_path, f"{cell_label} stage-c report")
    samples_sha256 = driver._verify_report(manifest, cell, report)
    if record.get("samples_sha256") != samples_sha256:
        raise ValueError(f"{cell_label} samples hash mismatch")

    gnu_time_path = record_path.parent / "gnu-time.txt"
    if not gnu_time_path.is_file():
        raise ValueError(f"{cell_label} complete record is missing gnu-time.txt")
    gnu_time_sha256 = driver.sha256_file(gnu_time_path)
    if record.get("gnu_time_sha256") != gnu_time_sha256:
        raise ValueError(f"{cell_label} GNU time hash mismatch")
    parsed_gnu_time = driver.parse_gnu_time(gnu_time_path.read_text(encoding="utf-8"))
    if record.get("gnu_time") != parsed_gnu_time:
        raise ValueError(f"{cell_label} GNU time record differs from its file")

    report_record = report["records"][0]
    phases = report_record["phases"]
    for phase, value in phases.items():
        _positive_number(value, f"{cell_label} phase {phase}")
    rss_kib = _positive_number(
        parsed_gnu_time.get("maximum_resident_set_kbytes"), f"{cell_label} RSS"
    )
    execution = record.get("execution")
    if not isinstance(execution, dict):
        raise ValueError(f"{cell_label} execution must be an object")
    process_wall_ns = _positive_number(execution.get("wall_ns"), f"{cell_label} process wall")
    return {"phases": phases, "rss_kib": rss_kib, "process_wall_ns": process_wall_ns}


def summarize(directory: Path) -> dict[str, Any]:
    directory = directory.resolve(strict=True)
    manifest = driver._load_frozen(directory)
    state = driver._load_object(directory / "state.json", "formal run state")
    manifest_sha256 = driver.sha256_file(directory / "manifest.json")
    if state.get("manifest_sha256") != manifest_sha256:
        raise ValueError("state manifest hash mismatch")
    schedule = manifest["schedule"]
    if state.get("cells_total") != len(schedule):
        raise ValueError("state cells_total differs from the frozen schedule")

    data: dict[tuple[str, int, str], dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    for cell in schedule:
        cell_dir = directory / "measurement" / f"cell-{cell['ordinal']:03d}"
        record_path = cell_dir / "record.json"
        if not record_path.is_file():
            missing.append(cell)
            incomplete.append(
                {"cell": cell, "evidence_status": "missing_record", "record_path": str(record_path)}
            )
            continue
        record = driver._load_object(record_path, f"cell-{cell['ordinal']:03d} record")
        if record.get("cell") != cell:
            raise ValueError(f"cell-{cell['ordinal']:03d} record identity mismatch")
        if record.get("status") != "complete":
            missing.append(cell)
            entry = {
                "cell": cell,
                "evidence_status": record.get("status", "missing_status"),
                "record_path": str(record_path),
            }
            if "failure" in record:
                entry["failure"] = record["failure"]
            if "available_files" in record:
                entry["available_files"] = record["available_files"]
            incomplete.append(entry)
            continue
        key = (cell["case_id"], cell["repeat"], cell["arm"])
        if key in data:
            raise ValueError(f"duplicate evidence cell identity: {key}")
        data[key] = _load_complete_cell(directory, manifest, cell, record_path, record)

    groups = []
    for case in manifest["cases"]:
        name = case["case_id"]
        group = {
            "case": name,
            "observation_level": case["observation_level"],
            "comparisons": [],
            "arm_medians": {},
        }
        for arm in ARMS:
            records = [data[name, repeat, arm] for repeat in range(3) if (name, repeat, arm) in data]
            if records:
                group["arm_medians"][arm] = {
                    "completed_repeats": len(records),
                    "phase_ns": {
                        phase: median(value["phases"][phase] for value in records)
                        for phase in records[0]["phases"]
                    },
                    "whole_process_peak_rss_kib": median(value["rss_kib"] for value in records),
                    "whole_process_wall_ns": median(
                        value["process_wall_ns"] for value in records
                    ),
                }
        for arm, control in COMPARISONS:
            pairs = []
            for repeat in range(3):
                arm_key = (name, repeat, arm)
                control_key = (name, repeat, control)
                if arm_key not in data or control_key not in data:
                    continue
                arm_data, control_data = data[arm_key], data[control_key]
                pairs.append(
                    {
                        "repeat": repeat,
                        "execution": arm_data["phases"]["batch_execution_ns"]
                        / control_data["phases"]["batch_execution_ns"],
                        "end_to_end": arm_data["phases"]["end_to_end_batch_ns"]
                        / control_data["phases"]["end_to_end_batch_ns"],
                        "rss": arm_data["rss_kib"] / control_data["rss_kib"],
                    }
                )
            row: dict[str, Any] = {
                "arm": arm,
                "control": control,
                "paired_ratios": pairs,
                "classification": "incomplete",
            }
            if len(pairs) == 3:
                ratios = {key: median(value[key] for value in pairs) for key in RATIO_KEYS}
                row["median_paired_ratios"] = ratios
                regression_measures = _regression_measures(ratios)
                if regression_measures:
                    row["classification"] = "regression"
                    row["regression_measures"] = regression_measures
                elif (
                    ratios["execution"] <= 0.95
                    and ratios["end_to_end"] <= 0.95
                    and ratios["rss"] <= 1.05
                    and all(value["end_to_end"] < 1 for value in pairs)
                ):
                    row["classification"] = "bounded-benefit"
                else:
                    row["classification"] = "no-demonstrated-benefit"
            group["comparisons"].append(row)
        groups.append(group)

    complete = state.get("status") == "complete" and len(data) == len(schedule)
    return {
        "schema_version": "three-arm-summary/v1",
        "formal_status": "complete" if complete else "incomplete",
        "recorded_state_status": state.get("status"),
        "elapsed_seconds": state.get("elapsed_seconds"),
        "complete_cells": len(data),
        "planned_cells": len(schedule),
        "unmeasured_cells": missing,
        "incomplete_cells": incomplete,
        "groups": groups,
        "default_adoption": "unchanged; no authorization",
        "limits": [
            "N=3, threads=1 only; not 32/256 scaling",
            "three repeats and three distinct seeds; no confidence intervals",
            "batch execution bundles preparation, initialization and execution",
            "whole-process RSS includes warmup and duplicate executions",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = summarize(args.directory)
    args.output.write_text(json.dumps(value, indent=2) + "\n")
    print(
        json.dumps(
            {
                "status": value["formal_status"],
                "completed": value["complete_cells"],
                "planned": value["planned_cells"],
            }
        )
    )


if __name__ == "__main__":
    main()
