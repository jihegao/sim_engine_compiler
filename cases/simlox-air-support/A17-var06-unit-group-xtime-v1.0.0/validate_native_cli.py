"""Bounded child verdict from sealed original outputs; never calls SIMLOX."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_roundtrip import validate as validate_roundtrip
from event_ledger import verify_file as verify_log
from model_common import INPUT_SHA, NATIVE_DIR, RUN_DIR, RUN_ID, seal
from report_oracle import compare_file
from source_gate import verify as verify_source


def validate(run: Path) -> dict:
    assert run == RUN_DIR and run.is_dir()
    verify_source()
    export = validate_roundtrip(run, source=False)
    log = verify_log(run / "model.log")
    report = compare_file(run / "report-raw.json")
    assert log["physical_lines"] == 60 and log["timed_lines"] == 52
    assert report["typed_cells"] == 4966 and report["stotd"] == 1
    return {
        "schema": "a17-var06-native-behavior-check/v100",
        "passed": True, "run_id": RUN_ID, "native_run_directory": NATIVE_DIR,
        "input_sha256": INPUT_SHA, "export_sha256": export["export_sha256"],
        "log_sha256": seal(run / "model.log")["sha256"],
        "report_sha256": report["raw_sha256"],
        "physical_log_lines": 60, "timed_log_lines": 52,
        "report_typed_cells": 4966, "stotd": 1,
        "authored_cells": 203, "exported_cells": 387,
        "native_calls": 0, "issues": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run_dir), sort_keys=True))


if __name__ == "__main__":
    main()
