"""Build a frozen C07 elapsed-hour-24 boundary candidate from an accepted parent."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-cross-shift-gap-v1.0.0" / "draos-n-input.json"
PARENT_SHA256 = "5674f271d59e1026d16c094ea08f78b59fdb50c9e4d818cb35e48d57edd2faad"
OUTPUT = HERE / "cross-day-input.json"


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

    put("ProblemDescription", 0, "PDESC",
        "C07 long crew work across 08-09 shift and 09-10 gap; DRAOS=N",
        "C07 two explicit crew shifts across elapsed hour 24; DRAOS=N")
    put("ShiftProfile", 0, "STIM", 8.0, 23.0)
    put("ShiftProfile", 0, "ETIM", 9.0, 24.0)
    put("ShiftProfile", 1, "STIM", 10.0, 25.0)
    put("ShiftProfile", 1, "ETIM", 11.0, 27.0)
    put("ShiftResource", 0, "QTY", 1, 2)
    put("OperationProfile", 0, "STIM", 12.0, 28.0)
    assert tables["Control"]["instances"][0]["rows"][0][17] == "N"
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
