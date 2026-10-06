"""Require only removal of accepted B02's two authored TaskBreakDown rows."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
CHILD_SHA = "7596ea50dc770bf9726a0d3300c0c2b0a881b772e57db0c3a079a3629714a939"


def main():
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(CHILD.read_bytes()).hexdigest() == CHILD_SHA
    parent = json.loads(PARENT.read_bytes())
    child = json.loads(CHILD.read_bytes())
    expected = copy.deepcopy(parent)
    tables = [t for t in expected["model"]["tables"] if t["name"] == "TaskBreakDown"]
    assert len(tables) == 1 and len(tables[0]["instances"]) == 1
    rows = tables[0]["instances"][0]["rows"]
    assert len(rows) == 2 and len(rows[0]) == len(tables[0]["columns"])
    assert len(rows[1]) == len(tables[0]["columns"])
    original_cells = sum(len(t["columns"]) * sum(len(i["rows"]) for i in t["instances"])
                         for t in parent["model"]["tables"])
    assert original_cells == 185
    removed = copy.deepcopy(rows)
    tables[0]["instances"][0]["rows"] = []
    if child != expected:
        raise ValueError("child has changes beyond the two TaskBreakDown row deletions")
    print(json.dumps({"schema": "simlox-b02-var06-parent-diff/v1", "passed": True,
                      "parent_cells": original_cells, "removed_cells": 2 * len(tables[0]["columns"]),
                      "removed_rows": removed}, ensure_ascii=True))


if __name__ == "__main__":
    main()
