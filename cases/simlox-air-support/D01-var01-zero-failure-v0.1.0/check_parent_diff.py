"""Check the exact D01 zero-FRT child delta without native execution."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
CHILD_SHA = "f9b1d2120de85307458dfddd92f69d7fa4bec9dd7bc5ee88c06c99b9cc338786"


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
    expected = {("System", 0, 0, "FRT"), ("Item", 0, 0, "FRT"),
                ("ProblemDescription", 0, 0, "PDESC")}
    if {tuple(c[k] for k in ("table", "instance", "row", "column")) for c in changes} != expected:
        raise ValueError(f"unexpected changes: {changes}")
    if any(c["before"] != 300000 or c["after"] != 0 for c in changes if c["column"] == "FRT"):
        raise ValueError("unexpected FRT delta")
    print(json.dumps({"schema": "simlox-d01-var01-parent-diff/v1", "parent_sha256": PARENT_SHA,
                      "child_sha256": CHILD_SHA, "same_cell_keys": len(old_cells),
                      "changes": changes}, indent=2))


if __name__ == "__main__":
    main()
