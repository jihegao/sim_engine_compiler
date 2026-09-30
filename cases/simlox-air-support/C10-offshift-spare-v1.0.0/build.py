"""Derive an on-shift idle spare versus one off-shift spare C10 pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C10-resource-failure-v1.0.0" / "oper-one-spare-input.json"
PARENT_SHA = "e34ce47cc2d26fa74fb9a90766cfd426caae0ff7b4a7fc75038867762d7b4278"
SCHEMA_SOURCE = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
SCHEMA_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"


def build() -> dict[str, dict]:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(SCHEMA_SOURCE.read_bytes()).hexdigest() == SCHEMA_SHA
    parent = json.loads(PARENT.read_bytes())
    template = json.loads(SCHEMA_SOURCE.read_bytes())
    parent_tables = {table["name"]: table for table in parent["model"]["tables"]}
    schema_tables = {table["name"]: table for table in template["model"]["tables"]}
    assert all(name not in parent_tables for name in ("Shift", "ShiftProfile", "ShiftResource"))
    assert parent_tables["ResourceAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "P-CREW", "BASE-01", 3, None]]
    assert parent_tables["ResourceStationData"]["instances"][0]["rows"] == [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, None, None]]
    assert [c["name"] for c in parent_tables["Control"]["columns"]][17] == "DRAOS"
    result = {}
    for variant, onshift in (("onshift-three", 3), ("onshift-two-offshift-one", 2)):
        child = copy.deepcopy(parent)
        tables = {table["name"]: table for table in child["model"]["tables"]}
        tables["ProblemDescription"]["instances"][0]["rows"][0][0] = f"C10 operation-time failure; three allocated crew; {onshift} on shift, seed 1"
        tables["Control"]["instances"][0]["rows"][0][17] = "N"
        tables["ResourceStationData"]["instances"][0]["rows"][0][9] = "CREW-DAY"
        shift = copy.deepcopy(schema_tables["Shift"])
        shift["instances"][0]["rows"] = [["DAY-OPEN", "Crew scheduled 7 to 10", None]]
        profile = copy.deepcopy(schema_tables["ShiftProfile"])
        profile["instances"][0]["rows"] = [["CREW-DAY", "DAY-OPEN", 7, 10, 1, None, None]]
        staffing = copy.deepcopy(schema_tables["ShiftResource"])
        staffing["instances"][0]["rows"] = [["DAY-OPEN", "BASE-01", "P-CREW", onshift, None, None]]
        child["model"]["tables"].extend((shift, profile, staffing))
        result[variant] = child
    return result


def main() -> None:
    for variant, doc in build().items():
        raw = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {variant} source differs"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
