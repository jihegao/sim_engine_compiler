"""Require exactly MaterielPM.PMINT 3-to-4 in the frozen D04 child."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D04-flight-hour-pm-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a"
CHILD_SHA = "cb8d6045df3b395583e3df2290b61376afa4fa9e8bc82a1c6f53fcfb44e2bddd"


def cells(doc: dict) -> dict:
    result = {}
    for table in doc["model"]["tables"]:
        for instance_index, instance in enumerate(table["instances"]):
            columns = [column["name"] for column in table["columns"]]
            for row_index, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular table")
                for field, value in zip(columns, row):
                    key = (table["name"], instance_index, row_index, field)
                    if key in result:
                        raise ValueError(f"duplicate source cell {key}")
                    result[key] = value
    return result


def main() -> None:
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D04 source SHA differs")
    if hashlib.sha256(CHILD.read_bytes()).hexdigest() != CHILD_SHA:
        raise ValueError("child source SHA differs")
    old, new = cells(json.loads(PARENT.read_bytes())), cells(json.loads(CHILD.read_bytes()))
    if old.keys() != new.keys():
        raise ValueError("authored source cell keys differ")
    changes = {key: (old[key], new[key]) for key in old if old[key] != new[key]}
    expected = {("MaterielPM", 0, 0, "PMINT"): (3.0, 4.0)}
    if changes != expected:
        raise ValueError(f"unexpected source delta: {changes!r}")
    print(json.dumps({"schema": "simlox-d04-var01-v010-parent-diff/v1", "passed": True,
                      "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA,
                      "cell_count": len(old), "changes": [{"key": key, "before": values[0],
                                                             "after": values[1]}
                                                            for key, values in changes.items()]}, indent=2))


if __name__ == "__main__":
    main()
