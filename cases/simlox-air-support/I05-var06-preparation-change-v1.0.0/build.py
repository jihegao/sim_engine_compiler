"""Freeze an in-progress versus later mission-preparation change from B01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
PARENT_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> str:
    assert arm in ("control", "change")
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {t["name"]: t for t in tables}
    assert len(by_name) == len(tables) == 31
    preparation = rows(by_name["MissionPreparation"])
    assert preparation == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 0.5, "PREP-FIXED", None, None]]
    preparation[0][3] = 4.0
    task = rows(by_name["Tasks"])
    assert task == [["PREP-FIXED", "Fixed 30-minute BASIC-MISSION preparation", None, None, None]]
    task[0][1] = "BASIC-MISSION preparation with scheduled duration change"
    profile = rows(by_name["OperationProfile"])
    assert profile == [["BASIC-SCHEDULE", "BASIC-MISSION", 8.0, "SCHEDULED", 1, None, 0, None, 1 / 3, None, None, None]]
    mission_type = rows(by_name["MissionType"])
    assert mission_type[0][0] == "BASIC-MISSION" and mission_type[0][12] == 1.0
    mission_type[0][12] = 4.0
    profile[0][2] = 13.0
    second = profile[0].copy()
    second[2] = 24.0
    profile.append(second)
    assert rows(by_name["ProblemDescription"]) == [["A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"]]
    rows(by_name["ProblemDescription"])[0][0] = f"I05.var06 {arm}: running preparation versus later changed duration"
    change = {
        "name": "ChangesMissionPreparation",
        "columns": [
            {"name": name, "datatype": dtype, **({"key": True} if name in ("MTID", "SID", "STID", "TIMEC") else {})}
            for name, dtype in (
                ("MTID", "string"), ("SID", "string"), ("STID", "string"),
                ("TIMEC", "double"), ("DURN", "double"), ("DURND", "string"), ("NOTE", "string")
            )
        ],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 7],
            "change": [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 10.0, 1.0, None, None]],
        }[arm]}],
    }
    tables.insert(tables.index(by_name["MissionPreparation"]) + 1, change)
    out = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == out, f"frozen {arm} source differs"
    else:
        target.write_bytes(out)
    return hashlib.sha256(out).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "change"):
        print(arm, make(arm))
