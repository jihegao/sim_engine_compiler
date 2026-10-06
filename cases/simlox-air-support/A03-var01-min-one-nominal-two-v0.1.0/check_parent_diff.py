"""Require exactly one MissionType.MNOS change among 155 authored cells."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-var01-one-of-two-v0.1.0/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "6b5807f42006a85f63777529d258ea1b563e5747f527821ab704f05f1d696709"
CHILD_SHA = "87778568dfb1ff7f8b367d2a936fc10c0653f784dd595dec9ebe7a46f36b4b13"


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
    expected = {("MissionType", 0, 0, "MNOS"): [2, 1]}
    if changes != expected:
        raise ValueError(f"one-cell source delta differs: {changes}")
    print(json.dumps({"schema": "simlox-a03-var01-min-one-parent-diff/v1", "passed": True,
                      "cells": 155, "changes": [{"cell": list(k), "values": v}
                                                for k, v in changes.items()]}))


if __name__ == "__main__":
    main()
