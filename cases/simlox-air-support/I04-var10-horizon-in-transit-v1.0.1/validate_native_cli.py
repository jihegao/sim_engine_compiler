"""Bounded h11 behavior gate against one sealed native child."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_roundtrip import validate as validate_export
from event_ledger import validate as validate_log
from model_common import pin
from report_oracle import validate as validate_report
from source_gate import HERE, RUN_DIR, RUN_ID, verify as verify_source


def validate(run: Path):
    assert run == RUN_DIR
    assert (run / "input.json").read_bytes() == (HERE / "native-input.json").read_bytes()
    source = verify_source("sealed")
    export = validate_export(run)
    log = validate_log((run / "model.log").read_bytes())
    report = validate_report((run / "report-raw.json").read_bytes())
    assert log["physical"]["microstates"] == 53
    assert log["physical"]["target_ready_terminal"] == 1
    assert log["physical"]["source_ready_terminal"] == 0
    assert log["physical"]["transit_terminal"] == 1
    assert log["physical"]["assigned_terminal"] == 0
    assert report["cells_checked"] == 1244 and report["horizon_bins"] == 22
    assert source["catalog"]["historical_prefix_checked"] == 499
    return {"schema": "i04-var10-horizon-transit-behavior/v101", "passed": True,
            "run_id": RUN_ID, "native_run_directory": str(RUN_DIR),
            "input_sha256": pin(run / "input.json")["sha256"],
            "export_sha256": export["export_sha256"], "report_cell_checks": 1244,
            "timed_event_records": log["timed_lines"], "log_lines": log["lines"],
            "terminal": log["physical"], "issues": [], "native_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    print(json.dumps(validate(parser.parse_args().run), sort_keys=True))
