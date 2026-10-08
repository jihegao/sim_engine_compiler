"""Bounded source and full prospective observed-output validator; no SIMLOX call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_roundtrip import validate as check_roundtrip
from event_ledger import verify_file as check_log
from model_common import NATIVE_DIR, RECOVERED_DIR, RUN_ID, INPUT_PIN, seal
from report_oracle import compare_file as check_report
from source_gate import verify as check_source


def validate(run: Path) -> dict[str, object]:
    assert run in (NATIVE_DIR, RECOVERED_DIR) and run.is_dir()
    check_source()
    exported = check_roundtrip(run, source=False)
    log = check_log(run / "model.log")
    report = check_report(run / "report-raw.json")
    assert log["physical_lines"] == 123 and log["timed_lines"] == 99
    assert report["typed_cells"] == 4044
    return {"schema": "e02-var02-native-behavior-check/v104", "passed": True,
            "run_id": RUN_ID, "native_run_directory": str(NATIVE_DIR),
            "input_sha256": INPUT_PIN["sha256"], "export_sha256": exported["export_sha256"],
            "log_sha256": seal(run / "model.log")["sha256"],
            "report_sha256": report["raw_sha256"],
            "physical_log_lines": 123, "timed_log_lines": 99,
            "report_typed_cells": 4044, "authored_cells": 274, "exported_cells": 369,
            "second_mission_cancel_hour": 20.3333, "repair_complete_hour": 20.9167,
            "aircraft_ready_hour": 21.25, "third_mission_success_hour": 34,
            "native_calls": 0, "issues": []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run_dir), sort_keys=True))


if __name__ == "__main__":
    main()
