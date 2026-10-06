"""Require the one-cell zero preparation delta from the accepted B01 input."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
CHILD_SHA = "5e2d473cdd617955e2920da0a473854a7576a041aa2653e65397dfc1746f1aee"


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
    expected = {("MissionPreparation", 0, 0, "DURN"): [0.5, 0]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-b01-var01-parent-diff/v1", "passed": True,
                      "cells": 167, "changes": [{"cell": list(key), "values": value}
                                                for key, value in changes.items()]}))


if __name__ == "__main__":
    main()
