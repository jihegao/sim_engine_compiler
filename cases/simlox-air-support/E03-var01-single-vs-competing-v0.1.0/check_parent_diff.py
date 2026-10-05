"""Verify the child changes only the declared E03 source cells."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E03-two-aircraft-shared-spare-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"
CHILD_SHA = "0fd7210b04aa8383a7288d3af0374fc96265c19f8d315612bee23a85c4d63879"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cells(doc):
    result = {}
    for t in doc["model"]["tables"]:
        for i, instance in enumerate(t["instances"]):
            for j, row in enumerate(instance["rows"]):
                for k, col in enumerate(t["columns"]):
                    key = (t["name"], i, j, col["name"])
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
    changes = [{"table": key[0], "instance": key[1], "row": key[2], "column": key[3], "before": old_cells[key], "after": new_cells[key]} for key in old_cells if old_cells[key] != new_cells[key]]
    expected = {("OperationProfile", 0, 0, "IQTY"), ("ProblemDescription", 0, 0, "PDESC")}
    if {tuple(item[k] for k in ("table", "instance", "row", "column")) for item in changes} != expected:
        raise ValueError(f"unexpected changes: {changes}")
    iq = next(item for item in changes if item["table"] == "OperationProfile")
    if iq["before"] != 2 or iq["after"] != 1:
        raise ValueError("unexpected IQTY delta")
    print(json.dumps({"schema": "simlox-e03-var01-parent-diff/v1", "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA, "same_cell_keys": len(old_cells), "changes": changes}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
