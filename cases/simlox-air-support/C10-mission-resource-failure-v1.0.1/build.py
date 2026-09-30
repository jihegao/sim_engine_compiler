"""Derive matched five-hour mission crew controls from accepted C05 capacity two."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C05-mission-resource-v1.0.0" / "capacity-2-input.json"
PARENT_SHA = "d2ea6e874eff82f1e50f271051010985c28adfba7aab94d2a0a0b343b989e865"
SCHEMA = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
SCHEMA_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"


def build() -> dict[str, dict]:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(SCHEMA.read_bytes()).hexdigest() == SCHEMA_SHA
    source = json.loads(PARENT.read_bytes())
    t = {table["name"]: table for table in source["model"]["tables"]}
    mission = t["MissionType"]["instances"][0]["rows"][0]
    assert mission[0] == "BASIC-MISSION" and mission[5] == 2.0
    assert t["ResourceAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "MISSION-CREW", "BASE-01", 2, None]]
    assert t["MissionResource"]["instances"][0]["rows"] == [["BASIC-MISSION", "TEACH-AIR-01", "MISSION-CREW", 1, None]]
    mission[1], mission[5] = "Five-hour generic mission", 5.0
    t["ProblemDescription"]["instances"][0]["rows"][0][0] = "C10 mission crew five-hour control; pool 2; seed 1"
    failure = copy.deepcopy(source)
    ft = {table["name"]: table for table in failure["model"]["tables"]}
    station = copy.deepcopy({table["name"]: table for table in json.loads(SCHEMA.read_bytes())["model"]["tables"]}["ResourceStationData"])
    assert [c["name"] for c in station["columns"]] == ["RID", "STID", "PRICE", "SUSTC", "MUTILF", "RMTBF", "RFTT", "RMDT", "RMDTD", "SHPID", "NOTE"]
    station["instances"][0]["rows"] = [["MISSION-CREW", "BASE-01", None, None, None, 3.0, "OPERATION", 0.25, None, None, None]]
    failure["model"]["tables"].append(station)
    ft["ProblemDescription"]["instances"][0]["rows"][0][0] = "C10 mission crew five-hour failure; pool 2; seed 1"
    return {"five-hour-control": source, "five-hour-failure": failure}


def main() -> None:
    for variant, doc in build().items():
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} input differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
