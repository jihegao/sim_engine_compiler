"""Require exactly the five authorized parent-to-child business-cell changes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
CHILD_SHA = "760cb41baca99d7fe3b8558a58c7330acb81944bb3d3ceba4e4241c06b9b9a00"


def cells(doc):
    found = {}
    for table in doc["model"]["tables"]:
        for instance_index, instance in enumerate(table["instances"]):
            columns = [c["name"] for c in table["columns"]]
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular table")
                for column, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, column)
                    if key in found:
                        raise ValueError(f"duplicate {key}")
                    found[key] = value
    return found


def main():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("parent SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("child SHA differs")
    old, new = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if old.keys() != new.keys():
        raise ValueError("table/cell keys differ")
    changes = {k: (old[k], new[k]) for k in old if old[k] != new[k]}
    expected = {
        ("ProblemDescription", 0, 0, "PDESC"):
            ("A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence",
             "D03.var01 one calendar-PM cycle through hour 36; no J35/F35 equivalence"),
        ("Control", 0, 0, "SIMPE"): (60.0, 36.0),
        ("Control", 0, 0, "RCEND"): (60.0, 36.0),
        ("ResultCollection", 0, 0, "RCEND"): (60.0, 36.0),
        ("ResultCollection", 0, 1, "RCEND"): (60.0, 36.0),
    }
    if changes != expected:
        raise ValueError(f"unexpected source changes: {changes!r}")
    print(json.dumps({"schema": "simlox-d03-var01-parent-diff/v1", "passed": True,
                      "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA,
                      "cell_count": len(old), "changes": [
                          {"key": k, "before": value[0], "after": value[1]}
                          for k, value in changes.items()]}, indent=2))


if __name__ == "__main__":
    main()
