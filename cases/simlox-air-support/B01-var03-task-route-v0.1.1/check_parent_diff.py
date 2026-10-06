"""Read-only exact B03-to-B01.var03 authored-cell check."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B03-explicit-cold-hot-v1.0.2" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "9c6b3c8955089b89caa1a71634eb78e9fd52069d5d710273e3a6bc710e19222c"
CHILD_SHA = "0cdb2bb68dcd49197988caba76b8d41e700b774139da98f33296c74c0d0d3c7b"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        columns = [field["name"] for field in table["columns"]]
        for ii, instance in enumerate(table["instances"]):
            for ri, row in enumerate(instance["rows"]):
                if len(columns) != len(row):
                    raise ValueError("nonrectangular authored row")
                for name, value in zip(columns, row, strict=True):
                    key = (table["name"], ii, ri, name)
                    if key in result:
                        raise ValueError("duplicate authored key")
                    result[key] = value
    return result


def main() -> None:
    assert digest(PARENT) == PARENT_SHA
    assert digest(CHILD) == CHILD_SHA
    parent = json.loads(PARENT.read_bytes())
    child = json.loads(CHILD.read_bytes())
    assert [t["name"] for t in parent["model"]["tables"]] == [t["name"] for t in child["model"]["tables"]]
    before, after = cells(parent), cells(child)
    assert len(before) == len(after) == 247
    assert list(before) == list(after)
    differences = [(key, before[key], after[key]) for key in before if before[key] != after[key]]
    assert differences == [(('OperationProfile', 0, 0, 'SPRID'), 'COLD-FIRST', 'HOT-SORTIE')]
    print(json.dumps({"passed": True, "authored_cells": len(after), "differences": differences,
                      "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA}))


if __name__ == "__main__":
    main()
