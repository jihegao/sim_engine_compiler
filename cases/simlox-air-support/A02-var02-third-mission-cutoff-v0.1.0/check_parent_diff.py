"""Require exactly SYSTEM ResultCollection.RCEND 36-to-33 among 179 cells."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions/native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
CHILD_SHA = "f7a2ff367b2d34294a6a0393fa83d040c8d01b433fc09e9d720f7483baa8d716"


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        columns = [c["name"] for c in table["columns"]]
        for instance_index, instance in enumerate(table["instances"]):
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular authored table")
                for field, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, field)
                    if key in result:
                        raise ValueError(f"duplicate authored cell {key}")
                    result[key] = value
    return result


def main():
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent source SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("frozen child source SHA differs")
    old, new = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if len(old) != 179 or old.keys() != new.keys():
        raise ValueError("authored cell topology differs")
    changes = {key: (old[key], new[key]) for key in old if old[key] != new[key]}
    if changes != {("ResultCollection", 0, 1, "RCEND"): (36.0, 33.0)}:
        raise ValueError(f"unexpected authored change: {changes!r}")
    print(json.dumps({"schema": "simlox-a02-var02-third-cutoff-v010-parent-diff/v1",
                      "passed": True, "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA,
                      "cell_count": len(old), "changes": [{"key": key, "before": values[0],
                                                      "after": values[1]} for key, values in changes.items()]}, indent=2))


if __name__ == "__main__":
    main()
