"""Deterministic two-cell source delta. Default invocation reads without writing."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from model_common import encode, pin, read, typed_equal, verify_expected

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I04-var01-system-between-v1.0.0" / "between-input.json"
CONTRACT = HERE / "prospective-contract.json"
INPUT = HERE / "native-input.json"
DELTA = HERE / "exact-diff.json"
PARENT_SHA = "50cc69df36afa0cecbbf8e6e7d699012f8987bb06bee11a1e347235d397da0ea"
CONTRACT_SHA = "7c0fd3dd20ab1f52eca3a47e5517f146469a1cec648d64b3ba4e5fbc3dbd1572"


def topology(model):
    tables = model["tables"]
    assert len({t["name"] for t in tables}) == len(tables)
    rows = cells = 0
    for table in tables:
        assert len(table["instances"]) == 1
        assert len({c["name"] for c in table["columns"]}) == len(table["columns"])
        instance = table["instances"][0]
        assert instance["instance_name"] == ""
        for row in instance["rows"]:
            assert len(row) == len(table["columns"])
            rows += 1
            cells += len(row)
    return {"tables": len(tables), "rows": rows, "cells": cells}


def make():
    assert pin(PARENT)["sha256"] == PARENT_SHA
    assert pin(CONTRACT)["sha256"] == CONTRACT_SHA
    source = read(PARENT)
    contract = read(CONTRACT)
    assert contract["state"] == "DRAFT_REQUIRES_INDEPENDENT_GO_NO_CASE_CONSTRUCTION_NO_NATIVE"
    assert source["model"]["database_version"] == contract["source"]["database_version"]
    assert topology(source["model"]) == {"tables": 34, "rows": 22, "cells": 223}
    result = copy.deepcopy(source)
    changes = []
    for spec in contract["source"]["changes"]:
        idx = spec["table_index"]
        table = result["model"]["tables"][idx]
        assert table["name"] == spec["table"]
        assert table["columns"][spec["column_index"]]["name"] == spec["column"]
        row = table["instances"][0]["rows"][spec["row"]]
        col = spec["column_index"]
        assert typed_equal(row[col], spec["parent"])
        row[col] = spec["child"]
        changes.append({"table_index": idx, "table": spec["table"], "row": spec["row"],
                        "column_index": col, "column": spec["column"],
                        "before": spec["parent"], "after": spec["child"]})
    assert len(changes) == 2
    assert topology(result["model"]) == topology(source["model"])
    original = copy.deepcopy(result)
    for spec in contract["source"]["changes"]:
        original["model"]["tables"][spec["table_index"]]["instances"][0]["rows"][spec["row"]][spec["column_index"]] = spec["parent"]
    assert typed_equal(original, source)
    delta = {"schema": "i04-var03-source-diff/v101", "parent": pin(PARENT),
             "contract": pin(CONTRACT), "topology": topology(result["model"]),
             "changes": changes, "all_other_metadata_and_cells_type_exact": True}
    return encode(result), encode(delta)


def run(write=False):
    input_body, delta_body = make()
    return {"schema": "i04-var03-build/v101", "input": verify_expected(INPUT, input_body, write),
            "diff": verify_expected(DELTA, delta_body, write), "native_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    print(json.dumps(run(parser.parse_args().write), sort_keys=True))
