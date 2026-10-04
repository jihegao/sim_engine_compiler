"""Freeze exact F03 risk-parent and one-LRU-stock pair deltas."""
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
    depot_only, forward_spare = build()
    tabs = lambda d: d["model"]["tables"]
    assert [x["name"] for x in tabs(parent)] == [x["name"] for x in tabs(depot_only)] == [x["name"] for x in tabs(forward_spare)]
    changed = [a["name"] for a, b in zip(tabs(parent), tabs(depot_only)) if a != b]
    paired = [a["name"] for a, b in zip(tabs(depot_only), tabs(forward_spare)) if a != b]
    assert changed == CHANGED and paired == ["ProblemDescription", "StockAllocation"]
    a, b = rows(depot_only, "StockAllocation"), rows(forward_spare, "StockAllocation")
    assert a[1:] == b[1:] and a[0][:3] == b[0][:3] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-01"]
    assert a[0][3] == 0 and b[0][3] == 1 and a[0][4:] == b[0][4:]
    assert rows(depot_only, "SystemDeployment")[-1][:3] == ["TEACH-AIR-01", "TEACH-UNIT-2", 1]
    result = {"schema": "simlox-f03-two-base-exact-diff/v1", "parent_changed_tables": changed,
              "pair_changed_tables": paired, "sole_business_pair_change": {"table": "StockAllocation", "row": 1,
              "station": "BASE-01", "item": "TEACH-LRU-01", "field": "STSIZ", "depot_only": 0, "forward_spare": 1},
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
