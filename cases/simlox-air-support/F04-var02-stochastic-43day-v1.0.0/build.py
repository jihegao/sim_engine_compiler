"""Freeze 128-replication F04 stochastic candidate from accepted F04.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F04-var01-deterministic-43day-v1.0.1" / "native-input.json"
PARENT_SHA = "7b9dfa927ba85c1260d9cbf6d58bae44914ad039a7b3b87b082e1ed04827cc4d"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]


def row(doc: dict, name: str) -> list:
    t = table(doc, name)
    assert len(t["instances"]) == 1
    result = t["instances"][0]["rows"]
    assert len(result) == 1
    return result[0]


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    doc = json.loads(raw)
    tables = doc["model"]["tables"]
    assert len(tables) == 32 and not any(t["name"] == "ReplicationResultControlSystem" for t in tables)
    control = table(doc, "Control")
    columns = [c["name"] for c in control["columns"]]
    values = row(doc, "Control")
    assert (values[columns.index("NREPS")], values[columns.index("TCLEV")],
            values[columns.index("SIMPE")]) == (1, None, 1032.0)
    assert row(doc, "System")[3] == 0
    item_rows = table(doc, "Item")["instances"][0]["rows"]
    assert [r[3] for r in item_rows] == [0, 0]
    missions = table(doc, "MissionType")["instances"][0]["rows"]
    assert [r[13] for r in missions] == [0, 0, 0]
    row(doc, "ProblemDescription")[0] = "F04.var02 v1.0.0 eight-aircraft 43-day stochastic risk replication"
    values[columns.index("NREPS")] = 128
    values[columns.index("TCLEV")] = 0.0
    row(doc, "System")[3] = 1000000.0
    for item in item_rows:
        item[3] = 1000000.0
    missions[1][13] = 1.0
    tables.append({
        "name": "ReplicationResultControlSystem",
        "columns": [
            {"datatype": "string", "key": True, "name": "SID"},
            {"datatype": "string", "key": True, "name": "USTID"},
            {"datatype": "string", "name": "TOTAL"},
            {"datatype": "string", "name": "TIME"},
            {"datatype": "string", "name": "SNAPS"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [
            ["TEACH-AIR-01", "TEACH-UNIT", "Y", "N", "N", None],
            ["TEACH-AIR-01", "TEACH-UNIT-2", "Y", "N", "N", None],
        ]}],
    })
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "native-input.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
