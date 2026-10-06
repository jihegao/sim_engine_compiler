"""Require the exact one-cell delta from accepted B02 1.0.2."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
CHILD_SHA = "2bc50fd4bc65a2036c85683605bb4eb6201ba0126902d3ffa33eb2106c1a8a46"


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        columns = [c["name"] for c in table["columns"]]
        for instance_index, instance in enumerate(table["instances"]):
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular authored table")
                for field, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, field)
                    if key in result:
                        raise ValueError(f"duplicate authored cell: {key}")
                    result[key] = value
    return result


def main():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("frozen child SHA differs")
    before, after = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if before.keys() != after.keys() or len(before) != 185:
        raise ValueError(f"authored cell topology differs: {len(before)}/{len(after)}")
    changes = {key: [before[key], after[key]] for key in before if before[key] != after[key]}
    expected = {("TaskBreakDown", 0, 0, "DURN"): [1 / 6, 0]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-b02-var01-parent-diff/v1", "passed": True,
                      "cells": len(before), "changes": [{"cell": list(key), "values": value}
                                                          for key, value in changes.items()]}))


if __name__ == "__main__":
    main()
