"""Require the one-cell NOPER delta from the accepted B01 input."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
CHILD_SHA = "1dcf6977f769693bb4e69639cfeb3f53f4277e56b238250078dd452b686fb319"


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        columns = [column["name"] for column in table["columns"]]
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
    if before.keys() != after.keys() or len(before) != 167:
        raise ValueError(f"authored cell topology differs: {len(before)}/{len(after)}")
    changes = {key: [before[key], after[key]] for key in before if before[key] != after[key]}
    expected = {("MissionType", 0, 0, "NOPER"): [1.0, 0.5]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-b01-var02-parent-diff/v1", "passed": True,
                      "cells": 167, "changes": [{"cell": list(key), "values": value}
                                                for key, value in changes.items()]}))


if __name__ == "__main__":
    main()
