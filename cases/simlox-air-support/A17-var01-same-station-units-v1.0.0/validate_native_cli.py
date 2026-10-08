"""Bounded pure child verdict from frozen original output; never calls SIMLOX."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_roundtrip import validate as validate_roundtrip
from event_ledger import semantic
from model_common import HERE, INPUT_SHA, NATIVE_DIR, RUN_DIR, RUN_ID, seal
from report_oracle import compare_file
from source_gate import verify as verify_source


def validate(run: Path) -> dict:
    assert run == RUN_DIR and run.is_dir()
    verify_source()
    export = validate_roundtrip(run, source=False)
    log = semantic((run / "model.log").read_bytes(), require_primary=True)
    report = compare_file(run / "report-raw.json")
    assert log["arm_status"] == "PRIMARY_CONTRACT_PASS_CANDIDATE"
    return {
        "schema": "a17-var01-native-behavior-check/v1",
        "passed": True, "run_id": RUN_ID, "native_run_directory": NATIVE_DIR,
        "input_sha256": INPUT_SHA, "export_sha256": export["export_sha256"],
        "log_sha256": seal(run / "model.log")["sha256"],
        "report_sha256": report["raw_sha256"],
        "full_log_lines": log["full_lines"], "timed_log_lines": log["timed_lines"],
        "log_arm": log["arm_id"], "report_typed_cells": report["typed_cells"],
        "exported_cells": export["exported_cells"],
        "ready_by_unit": log["ready_by_unit"],
        "native_calls": 0, "issues": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run_dir), sort_keys=True))


if __name__ == "__main__":
    main()
