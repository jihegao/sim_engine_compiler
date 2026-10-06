"""Require the exact one-cell delta from accepted B02 1.0.2."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
CHILD_SHA = "e408ff21a8dc9cb7c12ae5acd50d14089846299a4382e40303c9d68edc472d7e"


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
    expected = {("TaskBreakDown", 0, 0, "SUTID"): ["INSPECT", "<REPAIR>"]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-b02-var04-parent-diff/v1", "passed": True,
                      "cells": len(before), "changes": [{"cell": list(key), "values": value}
                                                          for key, value in changes.items()]}))


if __name__ == "__main__":
    main()
