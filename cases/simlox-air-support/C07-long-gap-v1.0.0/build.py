"""Build a frozen C07 48-hour off-shift-gap candidate from accepted cross-day."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-cross-day-v1.0.0" / "cross-day-input.json"
PARENT_SHA256 = "b3780ff767af1653372e8dbd3f367f1fef9829b5fbf324cf6f354a19df558046"
OUTPUT = HERE / "long-gap-input.json"


def build() -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {x["name"]: x for x in doc["model"]["tables"]}

    def put(table: str, row_index: int, column: str, old, new) -> None:
        t = tables[table]
        ix = [c["name"] for c in t["columns"]].index(column)
        row = t["instances"][0]["rows"][row_index]
        assert row[ix] == old, (table, row_index, column, row[ix], old)
        row[ix] = new

    put("ProblemDescription", 0, "PDESC", "C07 two explicit crew shifts across elapsed hour 24; DRAOS=N",
        "C07 two explicit crew shifts separated by 48 elapsed hours; DRAOS=N")
    put("Control", 0, "SIMPE", 36.0, 180.0)
    put("Control", 0, "RCEND", 36.0, 180.0)
    for i in (0, 1):
        put("ResultCollection", i, "RCEND", 36.0, 180.0)
    put("ShiftProfile", 0, "STIM", 23.0, 119.0)
    put("ShiftProfile", 0, "ETIM", 24.0, 120.0)
    put("ShiftProfile", 1, "STIM", 25.0, 168.0)
    put("ShiftProfile", 1, "ETIM", 27.0, 170.0)
    put("MissionType", 0, "NOPER", 4.5, 51.5)
    put("OperationProfile", 0, "STIM", 28.0, 171.0)
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == raw, "frozen candidate differs"
    else:
        OUTPUT.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
