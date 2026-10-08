"""Deterministic two-cell source delta. Default invocation reads without writing."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from model_common import encode, pin, read, typed_equal, verify_expected

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I04-var03-idle-system-between-v1.0.1" / "native-input.json"
CONTRACT = HERE / "prospective-contract.json"
INPUT = HERE / "native-input.json"
DELTA = HERE / "exact-diff.json"
EXPORT = HERE / "child-roundtrip-oracle.json"
PARENT_EXPORT = HERE.parent / "I04-var03-idle-system-between-v1.0.1" / "child-roundtrip-oracle.json"
REPORT = HERE / "child-report-oracle.json"
PROSPECTIVE_REPORT = HERE / "prospective-report-oracle.json"
PARENT_SHA = "48c346d27d9cd08be09a771292d198e00db72a19d488da5b184689504ace177b"
CONTRACT_SHA = "2353d18f907803c9023089e70202e7381cad266a0b8c7795bf98586ee067f292"
PARENT_EXPORT_SHA = "012913693d6af024f1a4176b0bc80a8229053bee6fb0ccfb75fd638c8da900c2"
PROSPECTIVE_REPORT_SHA = "9c8d75d91e58bff6438e8edc7e2f651226267fb83f2d8ae0bc9b98fb19ead64d"


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
    assert contract["phase"] == "RECOVERY_CONTRACT_DESIGN_ONLY_NO_NATIVE_AUTHORIZATION"
    assert source["model"]["database_version"] == contract["source"]["database_version"]
    assert topology(source["model"]) == {"tables": 34, "rows": 22, "cells": 223}
    result = copy.deepcopy(source)
    changes = []
    for spec in contract["source"]["differences"]:
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
    for spec in contract["source"]["differences"]:
        original["model"]["tables"][spec["table_index"]]["instances"][0]["rows"][spec["row"]][spec["column_index"]] = spec["parent"]
    assert typed_equal(original, source)
    delta = {"schema": "i04-var05-source-diff/v102", "parent": pin(PARENT),
             "contract": pin(CONTRACT), "topology": topology(result["model"]),
             "changes": changes, "all_other_metadata_and_cells_type_exact": True}
    return encode(result), encode(delta)


def export_oracle():
    assert pin(PARENT_EXPORT)["sha256"] == PARENT_EXPORT_SHA
    contract = read(CONTRACT)
    result = copy.deepcopy(read(PARENT_EXPORT))
    tables = result["model"]["tables"]
    assert len(tables) == 34
    assert sum(len(i["rows"]) for t in tables for i in t["instances"]) == 40
    assert sum(len(row) for t in tables for i in t["instances"] for row in i["rows"]) == 407
    assert tables[17]["name"] == "SystemTransfer"
    assert tables[0]["instances"][0]["rows"][0][0] == contract["source"]["differences"][0]["parent"]
    assert tables[17]["instances"][0]["rows"][0][5] == 0.5
    tables[0]["instances"][0]["rows"][0][0] = contract["source"]["differences"][0]["child"]
    tables[17]["instances"][0]["rows"][0][5] = 0.0
    return encode(result)


def report_oracle():
    assert pin(PROSPECTIVE_REPORT)["sha256"] == PROSPECTIVE_REPORT_SHA
    source = read(PROSPECTIVE_REPORT)
    assert source["schema"] == "i04-var05-prospective-full-report-oracle/v1"
    assert len(source["paired_differences"]) == 3
    expected = source["expected"]
    assert [t["name"] for t in expected["report"]["tables"]] == [
        "ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    assert sum(len(t["columns"]) * len(t["instances"][0]["rows"])
               for t in expected["report"]["tables"]) == 4044
    return encode(expected)


def run(write=False):
    input_body, delta_body = make()
    return {"schema": "i04-var05-build/v102", "input": verify_expected(INPUT, input_body, write),
            "diff": verify_expected(DELTA, delta_body, write),
            "export_oracle": verify_expected(EXPORT, export_oracle(), write),
            "report_oracle": verify_expected(REPORT, report_oracle(), write), "native_calls": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    print(json.dumps(run(parser.parse_args().write), sort_keys=True))
