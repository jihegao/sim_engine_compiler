"""Full authored and exported model comparison with one source-bound DIRPT delta."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from model_common import (HERE, REPO, RUN_ID, NATIVE_DIR, RECOVERED_DIR, INPUT_PIN,
                          compare_tables, count_model, exact, seal, strict_json, typed_value)
from source_gate import verify as verify_source

PARENT = REPO / "cases/simlox-air-support/E02-zero-stock-local-backorder-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_EXPORT = PARENT / "runs/e02-v100-ssh-20260929-01/roundtrip-raw.json"
PARENT_INPUT_PIN = {"bytes": 43699, "sha256": "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"}
PARENT_EXPORT_PIN = {"bytes": 57995, "sha256": "c4dad7079837d761dff5ac8285a84441cb2b21e0f8b1bb52d137f00bafdf935a"}
EXPORT_PIN = {"bytes": 46241, "sha256": "e1559006606357ad8525dc129ad77e9bdb52e7364da14143ab2ed302ae50990a"}


def changed_dirpt(parent: dict, child: dict, root: str, old: float, new: float) -> int:
    predicted = copy.deepcopy(parent)
    assert type(predicted) is dict and set(predicted) == {root}
    model = predicted[root]
    assert type(model) is dict and set(model) == {"database_version", "tables"}
    matches = [t for t in model["tables"] if t["name"] == "ItemRepair"]
    assert len(matches) == 1
    table = matches[0]
    assert len(table["instances"]) == 1 and len(table["instances"][0]["rows"]) == 1
    names = [column["name"] for column in table["columns"]]
    assert names[:3] == ["IID", "STID", "DIRPT"]
    row = table["instances"][0]["rows"][0]
    assert row[:3] == ["TEACH-LRU-01", "BASE-01", old]
    row[2] = new
    assert typed_value(predicted[root]["database_version"], child[root]["database_version"])
    return compare_tables(predicted[root]["tables"], child[root]["tables"])


def source_oracles() -> dict[str, object]:
    parent_input = strict_json(exact(PARENT_INPUT, PARENT_INPUT_PIN))
    child_input = strict_json(exact(HERE / "native-input.json", INPUT_PIN))
    parent_export = strict_json(exact(PARENT_EXPORT, PARENT_EXPORT_PIN))
    child_export = strict_json(exact(HERE / "child-roundtrip-oracle.json", EXPORT_PIN))
    assert count_model(parent_input, "model") == count_model(child_input, "model") == {
        "tables": 31, "rows": 24, "cells": 274}
    assert count_model(parent_export, "model") == count_model(child_export, "model") == {
        "tables": 31, "rows": 35, "cells": 369}
    assert changed_dirpt(parent_input, child_input, "model", 1.0, 10.75) == 274
    assert changed_dirpt(parent_export, child_export, "model", 1.0, 10.75) == 369
    return {"authored": 274, "exported": 369, "delta": "ItemRepair[TEACH-LRU-01,BASE-01].DIRPT 1.0 to 10.75"}


def validate(run: Path, source: bool = True) -> dict[str, object]:
    assert run in (NATIVE_DIR, RECOVERED_DIR) and run.is_dir(), str(run)
    if source:
        verify_source()
    source_oracles()
    expected_input = strict_json(exact(HERE / "native-input.json", INPUT_PIN))
    expected_export = strict_json(exact(HERE / "child-roundtrip-oracle.json", EXPORT_PIN))
    actual_input = strict_json((run / "input.json").read_bytes())
    actual_export = strict_json((run / "roundtrip-raw.json").read_bytes())
    assert seal(run / "input.json") == INPUT_PIN
    assert count_model(actual_input, "model") == {"tables": 31, "rows": 24, "cells": 274}
    assert count_model(actual_export, "model") == {"tables": 31, "rows": 35, "cells": 369}
    assert typed_value(expected_input["model"]["database_version"], actual_input["model"]["database_version"])
    assert typed_value(expected_export["model"]["database_version"], actual_export["model"]["database_version"])
    assert compare_tables(expected_input["model"]["tables"], actual_input["model"]["tables"]) == 274
    assert compare_tables(expected_export["model"]["tables"], actual_export["model"]["tables"]) == 369
    return {"schema": "e02-var02-roundtrip-check/v104", "passed": True,
            "run_id": RUN_ID, "native_run_directory": str(NATIVE_DIR),
            "input_sha256": INPUT_PIN["sha256"],
            "export_sha256": seal(run / "roundtrip-raw.json")["sha256"],
            "authored_tables": 31, "authored_rows": 24, "authored_cells": 274,
            "exported_tables": 31, "exported_rows": 35, "exported_cells": 369,
            "native_calls": 0, "issues": []}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run_dir), sort_keys=True))


if __name__ == "__main__":
    main()
