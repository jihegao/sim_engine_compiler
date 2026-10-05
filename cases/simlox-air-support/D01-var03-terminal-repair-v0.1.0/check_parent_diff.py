"""Check the exact D01.var03 parent-child business-cell delta."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
CHILD_SHA = "63c77c19f875b667db815999b17fd1e2ee053c6c0dbe620c2772b8175a387bac"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        for i, instance in enumerate(table["instances"]):
            for j, row in enumerate(instance["rows"]):
                if len(row) != len(table["columns"]):
                    raise ValueError("nonrectangular table")
                for k, column in enumerate(table["columns"]):
                    key = (table["name"], i, j, column["name"])
                    if key in result:
                        raise ValueError(f"duplicate cell {key}")
                    result[key] = row[k]
    return result


def main():
    if sha(PARENT) != PARENT_SHA or sha(CHILD) != CHILD_SHA:
        raise ValueError("input fingerprint differs")
    old = json.loads(PARENT.read_bytes())
    new = json.loads(CHILD.read_bytes())
    old_cells, new_cells = cells(old), cells(new)
    if old_cells.keys() != new_cells.keys():
        raise ValueError("table/cell shape differs")
    changes = [{"table": key[0], "instance": key[1], "row": key[2], "column": key[3],
                "before": old_cells[key], "after": new_cells[key]}
               for key in old_cells if old_cells[key] != new_cells[key]]
    expected = {("ProblemDescription", 0, 0, "PDESC"),
                ("Control", 0, 0, "SIMPE"), ("Control", 0, 0, "RCINT"),
                ("Control", 0, 0, "RCEND")}
    expected |= {("ResultCollection", 0, row, field) for row in (0, 1)
                 for field in ("RCINT", "RCEND")}
    if {tuple(c[k] for k in ("table", "instance", "row", "column")) for c in changes} != expected:
        raise ValueError(f"unexpected changes: {changes}")
    for change in changes:
        if change["column"] == "PDESC":
            continue
        before, after = (0.5, 0.25) if change["column"] == "RCINT" else (36.0, 34.25)
        if change["before"] != before or change["after"] != after:
            raise ValueError(f"unexpected {change['table']}.{change['column']} delta")
    print(json.dumps({"schema": "simlox-d01-var03-parent-diff/v1", "parent_sha256": PARENT_SHA,
                      "child_sha256": CHILD_SHA, "same_cell_keys": len(old_cells),
                      "changes": changes}, indent=2))


if __name__ == "__main__":
    main()
