"""Pure complete import/export comparison; no accepted checker or SIMLOX call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import (
    EXPORT_SHA, HERE, INPUT_SHA, NATIVE_DIR, RUN_DIR, RUN_ID, compare_tables, count_model,
    read_pinned_json, seal, strict_json, compare_typed,
)
from source_gate import verify as verify_source


def validate(run: Path, source: bool = True) -> dict:
    if source:
        verify_source()
    assert run == RUN_DIR and run.is_dir()
    expected_input = read_pinned_json(HERE / "native-input.json", INPUT_SHA)
    expected_export = read_pinned_json(HERE / "child-roundtrip-oracle.json", EXPORT_SHA)
    actual_input = strict_json((run / "input.json").read_bytes())
    actual_export = strict_json((run / "roundtrip-raw.json").read_bytes())
    assert seal(run / "input.json") == seal(HERE / "native-input.json")
    assert count_model(expected_input) == count_model(actual_input) == {"tables": 33, "rows": 20, "cells": 203}
    assert count_model(expected_export) == count_model(actual_export) == {"tables": 33, "rows": 38, "cells": 387}
    assert compare_typed(expected_input["model"]["database_version"], actual_input["model"]["database_version"])
    assert compare_typed(expected_export["model"]["database_version"], actual_export["model"]["database_version"])
    assert compare_tables(expected_input["model"]["tables"], actual_input["model"]["tables"]) == 203
    assert compare_tables(expected_export["model"]["tables"], actual_export["model"]["tables"]) == 387
    return {
        "schema": "a17-var01-roundtrip-check/v1", "passed": True,
        "run_id": RUN_ID, "native_run_directory": NATIVE_DIR,
        "input_sha256": INPUT_SHA,
        "export_sha256": seal(run / "roundtrip-raw.json")["sha256"],
        "authored_tables": 33, "authored_rows": 20, "authored_cells": 203,
        "exported_tables": 33, "exported_rows": 38, "exported_cells": 387,
        "native_calls": 0, "issues": [],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
