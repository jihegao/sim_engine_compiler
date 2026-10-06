"""Require exactly one A02 OperationProfile.STIM change for the at-return arm."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
CHILD_SHA = "c1aaf9c9387e37ad1e44f298b23bdf80b0c55c7f377168171e774a0874c52ca0"

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
    if len(old) != 179:
        raise ValueError(f"unexpected A02 authored cell count: {len(old)}")
    expected = {("OperationProfile", 0, 1, "STIM"): (20.0, 10.0)}
    if changes != expected:
        raise ValueError(f"unexpected source delta: {changes!r}")
    print(json.dumps({"schema": "simlox-a02-var01-at-return-v011-parent-diff/v1", "passed": True,
                      "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA,
                      "cell_count": len(old), "changes": [{"key": key, "before": values[0],
                                                             "after": values[1]}
                                                            for key, values in changes.items()]}, indent=2))

if __name__ == "__main__":
    main()
