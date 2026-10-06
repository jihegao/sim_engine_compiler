"""Require exactly the four resource and reporting rows declared for B04.var02."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-var05-turnround-breakdown-v0.1.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f"
CHILD_SHA = "0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5"


def cells(path):
    result = {}
    for table in json.loads(path.read_bytes())["model"]["tables"]:
        names = [column["name"] for column in table["columns"]]
        for instance_no, instance in enumerate(table["instances"]):
            for row_no, row in enumerate(instance["rows"]):
                if len(row) != len(names):
                    raise ValueError("nonrectangular table")
                for name, value in zip(names, row):
                    key = (table["name"], instance_no, row_no, name)
                    if key in result:
                        raise ValueError("duplicate authored cell")
                    result[key] = value
    return result


def main():
    for path, expected in ((PARENT, PARENT_SHA), (CHILD, CHILD_SHA)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"source bytes differ: {path}")
    before, after = cells(PARENT), cells(CHILD)
    expected_rows = {
        ("Resource", 0): ["P-CREW", "Turnround crew", None, None, None, "SPECIAL", None, None],
        ("ResourceAllocation", 0): ["AIR_BASIC", "P-CREW", "BASE-01", 1, None],
        ("SubTaskResource", 0): ["TURN-STEPS", 1, "P-CREW", 1, 1, None, None, None, None],
        ("ResultCollection", 2): ["RESOURCE", 0.5, 0, 36.0, None, None],
    }
    tables = {t["name"]: t for t in json.loads(CHILD.read_bytes())["model"]["tables"]}
    expected = {}
    for (table_name, row_no), row in expected_rows.items():
        names = [c["name"] for c in tables[table_name]["columns"]]
        expected.update({(table_name, 0, row_no, name): value for name, value in zip(names, row)})
    if before.keys() - after.keys():
        raise ValueError("parent cells removed")
    changed = {key: [before[key], after[key]] for key in before.keys() & after.keys()
               if before[key] != after[key]}
    added = {key: after[key] for key in after.keys() - before.keys()}
    if changed or added != expected:
        raise ValueError(f"delta differs: changed={changed}, added={added}")
    print(json.dumps({"schema": "simlox-b04-var02-parent-diff/v1", "passed": True,
                      "parent_cells": len(before), "child_cells": len(after),
                      "changed_cells": 0, "added_cells": len(added)}))


if __name__ == "__main__":
    main()
