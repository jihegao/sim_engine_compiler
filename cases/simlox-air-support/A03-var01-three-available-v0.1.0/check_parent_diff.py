"""Require exactly one A03 SystemDeployment.QTYPS change among 155 cells."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
CHILD_SHA = "6fc81a5a5ce9304c007a2087a0116cb585bf3fe70312649937e43d0576be0e71"


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        columns = [x["name"] for x in table["columns"]]
        for ii, instance in enumerate(table["instances"]):
            for ri, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular authored table")
                for field, value in zip(columns, row):
                    key = (table["name"], ii, ri, field)
                    if key in result:
                        raise ValueError(f"duplicate authored cell: {key}")
                    result[key] = value
    return result


def main():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A03 parent SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("frozen child SHA differs")
    before, after = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if before.keys() != after.keys() or len(before) != 155:
        raise ValueError(f"authored topology differs: {len(before)}/{len(after)}")
    changes = {key: [before[key], after[key]] for key in before if before[key] != after[key]}
    expected = {("SystemDeployment", 0, 0, "QTYPS"): [2, 3]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-a03-var01-parent-diff/v1", "passed": True,
                      "cells": 155, "changes": [{"cell": list(k), "values": v}
                                                for k, v in changes.items()]}))


if __name__ == "__main__":
    main()
