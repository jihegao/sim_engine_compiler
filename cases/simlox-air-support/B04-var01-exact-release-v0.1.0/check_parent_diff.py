"""Require exactly one B04 MissionTurnround.DURN change among 204 cells."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-cross-midnight-turnround-v1.0.1/turnround-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"
CHILD_SHA = "0a3525ca5eea07e7d642af9d4b8b36c3f607960a67375388a9d211d5138c3d16"


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
        raise ValueError("accepted B04 parent SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("frozen child SHA differs")
    before, after = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if before.keys() != after.keys() or len(before) != 204:
        raise ValueError(f"authored topology differs: {len(before)}/{len(after)}")
    changes = {key: [before[key], after[key]] for key in before if before[key] != after[key]}
    expected = {("MissionTurnround", 0, 0, "DURN"): [1.0, 0.75]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-b04-var01-parent-diff/v1", "passed": True,
                      "cells": 204, "changes": [{"cell": list(k), "values": v}
                                                for k, v in changes.items()]}))


if __name__ == "__main__":
    main()
