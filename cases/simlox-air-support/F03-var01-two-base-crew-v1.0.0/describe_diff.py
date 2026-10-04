"""Freeze exact F03 parent and one-resource pair deltas."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, build, rows

CHANGED = ["ProblemDescription", "Station", "StationStructure", "SystemDeployment", "SystemRepair",
           "MissionType", "OperationProfile", "Operations", "Unit", "MissionPreparation",
           "ResourceAllocation", "PMLocation", "StockAllocation", "MissionTurnround"]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    staffed, unstaffed = build()
    tabs = lambda d: d["model"]["tables"]
    assert [x["name"] for x in tabs(parent)] == [x["name"] for x in tabs(staffed)] == [x["name"] for x in tabs(unstaffed)]
    changed = [a["name"] for a, b in zip(tabs(parent), tabs(staffed)) if a != b]
    paired = [a["name"] for a, b in zip(tabs(staffed), tabs(unstaffed)) if a != b]
    assert changed == CHANGED and paired == ["ProblemDescription", "ResourceAllocation"]
    a, b = rows(staffed, "ResourceAllocation"), rows(unstaffed, "ResourceAllocation")
    assert a[:-1] == b[:-1] and a[-1] == ["AIR_BASIC", "P-CREW", "BASE-02", 1, None] and b[-1] == ["AIR_BASIC", "P-CREW", "BASE-02", 0, None]
    assert rows(staffed, "SystemDeployment")[-1][:3] == ["TEACH-AIR-01", "TEACH-UNIT-2", 1]
    result = {"schema": "simlox-f03-two-base-exact-diff/v1", "parent_changed_tables": changed,
              "pair_changed_tables": paired, "sole_business_pair_change": {"table": "ResourceAllocation", "row": 4,
              "station": "BASE-02", "resource": "P-CREW", "field": "RQTY", "staffed": 1, "unstaffed": 0},
              "parent_other_tables": "exactly unchanged", "two_units_same_system_type": "TEACH-AIR-01"}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw, "frozen diff changed"
    else:
        target.write_bytes(raw)
    print(sha(raw))


if __name__ == "__main__":
    main()
