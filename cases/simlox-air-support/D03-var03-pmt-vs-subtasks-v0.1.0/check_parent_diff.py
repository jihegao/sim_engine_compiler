"""Require the single authorized D03.var03 PMT source-cell change."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
CHILD_SHA = "59642b8ef5ac9e48c45110223b147cf776e0be4e0e8983a2e9507b1412074a36"


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        for i, instance in enumerate(table["instances"]):
            columns = [x["name"] for x in table["columns"]]
            for j, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular table")
                for field, value in zip(columns, row):
                    key = (table["name"], i, j, field)
                    if key in result:
                        raise ValueError(f"duplicate cell {key}")
                    result[key] = value
    return result


def main():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("parent source SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("child source SHA differs")
    old = cells(json.loads(PARENT.read_bytes()))
    new = cells(json.loads(CHILD.read_bytes()))
    if old.keys() != new.keys():
        raise ValueError("cell keys differ")
    changes = {key: (old[key], new[key]) for key in old if old[key] != new[key]}
    if changes != {("PMLocation", 0, 0, "PMT"): (1.0, 4.0)}:
        raise ValueError(f"unexpected source delta: {changes!r}")
    print(json.dumps({"schema": "simlox-d03-var03-parent-diff/v1", "passed": True,
                      "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA,
                      "cell_count": len(old), "changes": [{"key": key, "before": value[0], "after": value[1]}
                                                        for key, value in changes.items()]}, indent=2))


if __name__ == "__main__":
    main()
