"""Require exactly one TFOUT source-cell change for the sum-to-one arm."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
CHILD_SHA = "242d83ba901e7f64dc8a0ccefd4f5a405a51ede86359e240d4abb12bf543b1f9"

def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        for instance_index, instance in enumerate(table["instances"]):
            columns = [column["name"] for column in table["columns"]]
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular authored table")
                for field, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, field)
                    if key in result:
                        raise ValueError(f"duplicate source cell {key}")
                    result[key] = value
    return result

def main():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A01 input SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("frozen A01.var01 input SHA differs")
    old, new = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if old.keys() != new.keys():
        raise ValueError("authored source cell keys differ")
    changes = {key: (old[key], new[key]) for key in old if old[key] != new[key]}
    expected = {("MissionType", 0, 0, "TFOUT"): (0.25, 0.75)}
    if changes != expected:
        raise ValueError(f"unexpected source delta: {changes!r}")
    print(json.dumps({"schema": "simlox-a01-var01-sum-one-v010-parent-diff/v1", "passed": True,
                      "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA,
                      "cell_count": len(old), "changes": [{"key": key, "before": values[0],
                                                             "after": values[1]}
                                                            for key, values in changes.items()]}, indent=2))

if __name__ == "__main__":
    main()
