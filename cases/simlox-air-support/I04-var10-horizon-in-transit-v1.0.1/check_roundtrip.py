"""Exact 34-table/395-cell export gate; no simulator calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import numeric_equal, pin, read, typed_equal
from build import topology
from source_gate import RUN_DIR, RUN_ID

HERE = Path(__file__).resolve().parent
ORACLE = HERE / "child-roundtrip-oracle.json"


def compare(actual, expected, path="$"):
    assert isinstance(actual, dict) and list(actual) == list(expected), path
    assert isinstance(actual["model"], dict) and list(actual["model"]) == list(expected["model"]), path
    assert actual["model"]["database_version"] == expected["model"]["database_version"]
    assert type(actual["model"]["database_version"]) is int
    at = actual["model"]["tables"]
    et = expected["model"]["tables"]
    assert len(at) == len(et), path
    for ti, (a, e) in enumerate(zip(at, et)):
        where = f"{path}.model.tables[{ti}]"
        assert isinstance(a, dict) and list(a) == list(e), where
        assert a["name"] == e["name"] and type(a["name"]) is str, where
        assert typed_equal(a["columns"], e["columns"]), where + ".columns"
        assert len(a["instances"]) == len(e["instances"]) == 1, where
        ai, ei = a["instances"][0], e["instances"][0]
        assert list(ai) == list(ei) and ai["instance_name"] == ei["instance_name"] == "", where
        assert len(ai["rows"]) == len(ei["rows"]), where
        for ri, (ar, er) in enumerate(zip(ai["rows"], ei["rows"])):
            assert len(ar) == len(er) == len(a["columns"]), (where, ri)
            for ci, (av, ev) in enumerate(zip(ar, er)):
                dtype = a["columns"][ci]["datatype"]
                cell = f"{where}.rows[{ri}][{ci}]"
                if dtype == "double" and ev is not None:
                    assert numeric_equal(av, ev), cell
                else:
                    assert typed_equal(av, ev), cell


def validate(path: Path):
    if path.is_dir():
        run = path
        input_path = run / "input.json"
        assert input_path.read_bytes() == (HERE / "native-input.json").read_bytes()
        path = run / "roundtrip-raw.json"
    else:
        input_path = HERE / "native-input.json"
    expected = read(ORACLE)
    actual = read(path)
    assert set(expected) == {"model"}
    assert set(actual) == {"model"}
    tables = actual["model"]["tables"]
    assert len(tables) == 34
    assert topology(read(input_path)) == {"tables": 34, "rows": 21, "cells": 211}
    assert topology(actual) == {"tables": 34, "rows": 39, "cells": 395}
    assert tables[17]["name"] == "SystemTransfer"
    empty_input = {t["name"] for t in read(input_path)["model"]["tables"] if not t["instances"][0]["rows"]}
    assert len(empty_input) == 18
    for table in tables:
        if table["name"] in empty_input:
            assert table["instances"][0]["rows"] == [[None] * len(table["columns"])]
    compare(actual, expected)
    return {"schema": "i04-var10-horizon-transit-roundtrip/v101", "passed": True,
            "run_id": RUN_ID, "native_run_directory": str(RUN_DIR),
            "tables": 34, "authored_rows": 21, "exported_rows": 39,
            "authored_cells": 211, "exported_cells": 395,
            "all_null_placeholder_tables": 18, "issues": [],
            "input_sha256": pin(input_path)["sha256"], "export_sha256": pin(path)["sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    print(json.dumps(validate(parser.parse_args().path), sort_keys=True))
