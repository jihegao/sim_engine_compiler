"""Read-only source delta and complete 32-table native roundtrip gate."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

from json_codec import parse, typed_equal

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OLD = HERE.parent / "I03-var06-out-ignored-duration-v1.0.0"
AUTHORED = HERE / "preserved-v100-source" / "native-input.json"
PARENT = HERE.parent / "I03-var02-idle-crew-out-v1.0.2" / "native-input.json"
RUN = OLD / "runs" / "i03-var06-out-dt4-v100-ssh-20261008-01"
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
INPUT_SHA = "3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694"
PLACEHOLDERS = {"Item", "ItemStructure", "StationStructure", "SystemRepair", "ItemRepair",
                "ItemReorder", "TaskResource", "MaterielPM", "PMLocation", "StockAllocation", "ItemReplacement"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def flatten(model: dict) -> dict[str, object]:
    out = {}
    for table in model["tables"]:
        assert len(table["instances"]) == 1
        for i, row in enumerate(table["instances"][0]["rows"]):
            assert len(row) == len(table["columns"])
            for column, value in zip(table["columns"], row):
                key = f"{table['name']}[0,{i}].{column['name']}"
                assert key not in out
                out[key] = value
    return out


def shape(tables: list[dict]) -> None:
    assert len(tables) == 32 and len({t["name"] for t in tables}) == 32
    for table in tables:
        assert set(table) == {"name", "columns", "instances"}
        assert len(table["instances"]) == 1
        assert set(table["instances"][0]) == {"instance_name", "rows"}
        assert len({col["name"] for col in table["columns"]}) == len(table["columns"])
        for row in table["instances"][0]["rows"]:
            assert len(row) == len(table["columns"])


def rows_equal(columns: list[dict], authored: list[list], exported: list[list]) -> bool:
    if len(authored) != len(exported):
        return False
    for a, b in zip(authored, exported):
        if len(a) != len(columns) or len(b) != len(columns):
            return False
        for col, x, y in zip(columns, a, b):
            if col["datatype"] == "double" and x is not None:
                if type(x) not in (int, float) or type(y) not in (int, float) or not math.isfinite(y) or x != y:
                    return False
            elif not typed_equal(x, y):
                return False
    return True


def check(parent: dict | None = None, child: dict | None = None, exported: dict | None = None) -> dict:
    parent_pin = CONTRACT["source_delta"]["parent_input"]
    assert PARENT.stat().st_size == parent_pin["bytes"] and digest(PARENT) == parent_pin["sha256"]
    assert digest(AUTHORED) == digest(RUN / "input.json") == INPUT_SHA
    if (OLD / "native-input.json").exists():
        assert digest(OLD / "native-input.json") == INPUT_SHA
    parent = parse(PARENT) if parent is None else parent
    child = parse(AUTHORED) if child is None else child
    exported = parse(RUN / "roundtrip-raw.json") if exported is None else exported
    assert set(parent) == set(child) == set(exported) == {"model"}
    pm, cm, em = parent["model"], child["model"], exported["model"]
    for model in (pm, cm, em):
        assert set(model) == {"database_version", "tables"}
        assert type(model["database_version"]) is int and model["database_version"] == 20160627
        shape(model["tables"])
    expected = copy.deepcopy(parent)
    pd = one(expected["model"], "ProblemDescription")
    assert pd["instances"][0]["instance_name"] == ""
    assert pd["instances"][0]["rows"] == [[CONTRACT["source_delta"]["allowed_changes_exactly"][0]["from"]]]
    pd["instances"][0]["rows"][0][0] = CONTRACT["source_delta"]["allowed_changes_exactly"][0]["to"]
    transfer = one(expected["model"], "ResourceTransfer")
    assert transfer["instances"][0]["instance_name"] == ""
    assert [c["name"] for c in transfer["columns"]] == ["STFID", "STTID", "RID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    assert transfer["instances"][0]["rows"] == [["BASE-01", "<OUTSIDE>", "P-CREW", 6.0, 1, 0.0, None]]
    transfer["instances"][0]["rows"][0][5] = 4.0
    assert typed_equal(child, expected), "authored two-cell source or metadata drift"
    before, after = flatten(pm), flatten(cm)
    assert before.keys() == after.keys()
    changes = [(name, before[name], after[name]) for name in before if not typed_equal(before[name], after[name])]
    assert changes == [("ProblemDescription[0,0].PDESC",
                        CONTRACT["source_delta"]["allowed_changes_exactly"][0]["from"],
                        CONTRACT["source_delta"]["allowed_changes_exactly"][0]["to"]),
                       ("ResourceTransfer[0,0].TFDT", 0.0, 4.0)]
    at, et = cm["tables"], em["tables"]
    assert [t["name"] for t in at] == [t["name"] for t in et]
    populated = 0
    placeholders = set()
    for a, e in zip(at, et):
        assert typed_equal(a["columns"], e["columns"])
        assert typed_equal([i["instance_name"] for i in a["instances"]], [i["instance_name"] for i in e["instances"]])
        ar, er = a["instances"][0]["rows"], e["instances"][0]["rows"]
        if ar:
            populated += 1
            assert a["name"] not in PLACEHOLDERS and rows_equal(a["columns"], ar, er), a["name"]
        else:
            placeholders.add(a["name"])
            assert er == [[None] * len(a["columns"])], a["name"]
    assert populated == 21 and placeholders == PLACEHOLDERS
    receipt = parse(RUN / "roundtrip-validation.json")
    assert set(receipt) == {"schema", "passed", "issues", "input_sha256", "export_sha256",
                            "table_objects", "row_containing_tables", "all_null_placeholder_tables"}
    assert receipt["schema"] == "i03-var06-out-dt4-roundtrip/v1" and receipt["passed"] is True and receipt["issues"] == []
    assert receipt["input_sha256"] == INPUT_SHA and receipt["export_sha256"] == digest(RUN / "roundtrip-raw.json")
    assert (receipt["table_objects"], receipt["row_containing_tables"], receipt["all_null_placeholder_tables"]) == (32, 21, 11)
    return {"source_cells": len(before), "source_changes": len(changes), "roundtrip_tables": 32,
            "populated_tables": populated, "placeholder_tables": len(placeholders), "export_sha256": receipt["export_sha256"]}
