"""Require the sole ResourceAllocation.RQTY 1→0 child delta."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-var02-turnround-resource-v0.1.1" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5"
CHILD_SHA = "fa7b9040fced6267aa5781cb0761df41b803c0cccaf8c218a2aa0c1de01b24bb"


def cells(path):
    result = {}
    for table in json.loads(path.read_bytes())["model"]["tables"]:
        names = [c["name"] for c in table["columns"]]
        for instance_no, instance in enumerate(table["instances"]):
            for row_no, row in enumerate(instance["rows"]):
                if len(row) != len(names):
                    raise ValueError("nonrectangular table")
                for name, value in zip(names, row):
                    key = (table["name"], instance_no, row_no, name)
                    if key in result:
                        raise ValueError("duplicate cell")
                    result[key] = value
    return result


def main():
    for path, expected in ((PARENT, PARENT_SHA), (CHILD, CHILD_SHA)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen source bytes differ: {path}")
    before, after = cells(PARENT), cells(CHILD)
    changed = {key: [before[key], after[key]] for key in before.keys() & after.keys()
               if before[key] != after[key]}
    expected = {("ResourceAllocation", 0, 0, "RQTY"): [1, 0]}
    if changed != expected or before.keys() != after.keys() or len(before) != 249:
        raise ValueError(f"source diff differs: {changed}")
    print(json.dumps({"schema": "simlox-b04-var02-zero-crew-parent-diff/v1",
                      "passed": True, "parent_cells": 249, "child_cells": 249,
                      "changed": [[*key, values] for key, values in changed.items()]}))


if __name__ == "__main__":
    main()
