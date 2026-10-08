"""Bounded child behavior acceptance, read-only against one sealed native run."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_roundtrip import validate as validate_export
from event_ledger import validate as validate_log
from model_common import pin
from report_oracle import validate as validate_report
from source_gate import HERE, RUN_ID, verify as verify_source


def validate(run: Path):
    assert run.name == RUN_ID and run.parent == HERE / "runs"
    assert (run / "input.json").read_bytes() == (HERE / "native-input.json").read_bytes()
    source = verify_source("sealed")
    export = validate_export(run)
    log = validate_log((run / "model.log").read_bytes())
    report = validate_report((run / "report-raw.json").read_bytes(), True)
    assert log["physical"] == {
        "ready_edges": 12, "terminal_source_ready": 0, "terminal_target_ready": 2,
        "terminal_transit": 0, "terminal_assigned": 0,
    }
    assert report["cells_checked"] == 4044 and report["paired_differences"] == 5
    assert source["catalog"]["historical_prefix_checked"] == 496
    return {"schema": "i04-var03-idle-between-behavior/v101", "passed": True,
            "run_id": RUN_ID, "input_sha256": pin(run / "input.json")["sha256"],
            "export_sha256": export["export_sha256"], "report_cell_checks": 4044,
            "paired_differences": 5, "timed_event_records": log["timed_lines"],
            "log_lines": log["lines"], "optional_diagnostics": {
                "empty_source_ready": log["optional_ready_zero"],
                "empty_source_priority": log["optional_priority"],
            }, "terminal": log["physical"], "issues": [], "native_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    print(json.dumps(validate(parser.parse_args().run), sort_keys=True))
