"""Verify the exact authored delta from accepted B04 turnround v1.0.1."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B04-cross-midnight-turnround-v1.0.1" / "turnround-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"
CHILD_SHA = "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f"


def cells(doc):
    result = {}
    for table in doc["model"]["tables"]:
        columns = [column["name"] for column in table["columns"]]
        for instance_no, instance in enumerate(table["instances"]):
            for row_no, row in enumerate(instance["rows"]):
                if len(row) != len(columns):
                    raise ValueError("nonrectangular source table")
                for column, value in zip(columns, row):
                    key = (table["name"], instance_no, row_no, column)
                    if key in result:
                        raise ValueError("duplicate authored cell")
                    result[key] = value
    return result


def main():
    for path, expected in ((PARENT, PARENT_SHA), (CHILD, CHILD_SHA)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen source bytes differ: {path}")
    before = cells(json.loads(PARENT.read_bytes()))
    after = cells(json.loads(CHILD.read_bytes()))
    changed = {key: [before[key], after[key]] for key in before.keys() & after.keys()
               if before[key] != after[key]}
    added = {key: after[key] for key in after.keys() - before.keys()}
    removed = before.keys() - after.keys()
    expected_changed = {("MissionTurnround", 0, 0, "TID"): [None, "TURN-STEPS"]}
    expected_added = {
        ("Tasks", 0, 1, "TID"): "TURN-STEPS",
        ("Tasks", 0, 1, "DESCR"): "Serial 10+20-minute post-mission turnround",
        ("Tasks", 0, 1, "TCID"): None,
        ("Tasks", 0, 1, "TLID"): None,
        ("Tasks", 0, 1, "NOTE"): None,
    }
    for row_no, seq, subtask, duration in ((2, 1, "INSPECT", 1 / 6),
                                            (3, 2, "SERVICE", 1 / 3)):
        expected_added.update({
            ("TaskBreakDown", 0, row_no, "TID"): "TURN-STEPS",
            ("TaskBreakDown", 0, row_no, "SEQ"): seq,
            ("TaskBreakDown", 0, row_no, "SUTID"): subtask,
            ("TaskBreakDown", 0, row_no, "DURN"): duration,
            ("TaskBreakDown", 0, row_no, "DURND"): None,
            ("TaskBreakDown", 0, row_no, "NOTE"): None,
        })
    if changed != expected_changed or added != expected_added or removed:
        raise ValueError("source delta differs from the one-cell/three-row contract")
    print(json.dumps({"schema": "simlox-b04-var05-parent-diff/v1", "passed": True,
                      "parent_cells": len(before), "child_cells": len(after),
                      "changed_cells": len(changed), "added_cells": len(added),
                      "removed_cells": len(removed)}))


if __name__ == "__main__":
    main()
