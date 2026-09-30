"""Derive a long, capacity-limited C07 shift-gap candidate from accepted C07."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-offshift-boundary-v1.0.0" / "draos-y-input.json"
PARENT_SHA256 = "fc7ca3caeefee1190a8497c8e5a32a463a96d17c426d4d97ee57673b49405a94"


def build(draos: str) -> dict:
    assert draos in ("Y", "N")
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    t = {x["name"]: x for x in doc["model"]["tables"]}

    def row(table: str) -> list:
        rows = t[table]["instances"][0]["rows"]
        assert len(rows) == 1
        return rows[0]

    def put(table: str, column: str, old, new) -> None:
        names = [c["name"] for c in t[table]["columns"]]
        index = names.index(column)
        assert row(table)[index] == old, (table, column)
        row(table)[index] = new

    put("ProblemDescription", "PDESC", "C07 off-shift crew availability; DRAOS=Y",
        f"C07 long crew work across 08-09 shift and 09-10 gap; DRAOS={draos}")
    put("Control", "DRAOS", "Y", draos)
    put("MissionPreparation", "DURN", 0.5, 2.0)
    put("TaskBreakDown", "DURN", 0.5, 2.0)
    put("OperationProfile", "STIM", 8.0, 12.0)
    put("MissionType", "NOPER", 0.5, 4.5)
    put("Tasks", "DESCR", "Serial 10+20-minute BASIC-MISSION preparation",
        "Two-hour crew-dependent mission preparation")
    put("ShiftProfile", "STIM", 7.75, 8.0)
    put("ShiftProfile", "ETIM", 10.0, 9.0)
    assert row("ShiftProfile")[1] == "DAY-OPEN"
    t["ShiftProfile"]["instances"][0]["rows"].append(
        ["CREW-DAY", "DAY-OPEN", 10.0, 11.0, 1, None, None]
    )
    put("ShiftResource", "QTY", 2, 1)
    return doc


def main() -> None:
    for value in ("Y", "N"):
        path = HERE / f"draos-{value.lower()}-input.json"
        raw = (json.dumps(build(value), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {path}"
        else:
            path.write_bytes(raw)
        print(value, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
