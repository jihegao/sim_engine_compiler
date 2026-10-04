"""Build a two-base F03 local-LRU-stock pair from accepted F02 risk fleet."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2" / "risk-input.json"
PARENT_SHA = "ae46b08a6ef6fd063906b888fb3c73fba06edcb57acc1a4ade49fc62c53fd7d3"
A17 = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
A17_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(document: dict, name: str) -> dict:
    matches = [x for x in document["model"]["tables"] if x["name"] == name]
    assert len(matches) == 1, name
    return matches[0]


def rows(document: dict, name: str) -> list[list]:
    tab = table(document, name)
    assert len(tab["instances"]) == 1
    return tab["instances"][0]["rows"]


def build() -> tuple[dict, dict]:
    parent_raw, donor_raw = PARENT.read_bytes(), A17.read_bytes()
    assert sha(parent_raw) == PARENT_SHA and sha(donor_raw) == A17_SHA
    parent, donor = json.loads(parent_raw), json.loads(donor_raw)
    assert rows(parent, "Station")[0][0] == "BASE-01" and rows(parent, "Station")[1][0] == "DEPOT-01"
    assert rows(donor, "Station")[1][0] == "BASE-02" and rows(donor, "Unit")[1][0] == "TEACH-UNIT-2"
    child = copy.deepcopy(parent)
    rows(child, "ProblemDescription")[0][0] = "F03.var02 two bases, depot-only LRU stock control"
    rows(child, "Station").append(copy.deepcopy(rows(donor, "Station")[1]))
    route = copy.deepcopy(rows(parent, "StationStructure")[0])
    route[0] = "BASE-02"
    rows(child, "StationStructure").append(route)
    rows(child, "Unit").append(["TEACH-UNIT-2", "One-aircraft second-base teaching unit", "BASE-02", 1, None, None])
    deployment = copy.deepcopy(rows(parent, "SystemDeployment")[0])
    deployment[1:3] = ["TEACH-UNIT-2", 1]
    rows(child, "SystemDeployment").append(deployment)
    mission = copy.deepcopy(rows(parent, "MissionType")[0])
    mission[0:4] = ["BASE2-MISSION", "Second-base two-hour single-aircraft mission", 1, 1]
    rows(child, "MissionType").append(mission)
    profile = copy.deepcopy(rows(parent, "OperationProfile")[1])
    profile[0:3] = ["BASE2-SCHEDULE", "BASE2-MISSION", 8.0]
    profile[8] = 1.0
    rows(child, "OperationProfile").append(profile)
    rows(child, "Operations").append(["TEACH-UNIT-2", "BASE2-SCHEDULE", None])
    prep = copy.deepcopy(rows(parent, "MissionPreparation")[0])
    prep[0:3] = ["BASE2-MISSION", "TEACH-AIR-01", "BASE-02"]
    rows(child, "MissionPreparation").append(prep)
    turn = copy.deepcopy(rows(parent, "MissionTurnround")[0])
    turn[0:3] = ["BASE2-MISSION", "TEACH-AIR-01", "BASE-02"]
    rows(child, "MissionTurnround").append(turn)
    repair = copy.deepcopy(rows(parent, "SystemRepair")[0])
    repair[1] = "BASE-02"
    rows(child, "SystemRepair").append(repair)
    pm = copy.deepcopy(rows(parent, "PMLocation")[0])
    pm[2] = "BASE-02"
    rows(child, "PMLocation").append(pm)
    resource = rows(child, "ResourceAllocation")
    assert resource == [["AIR_BASIC", "P-MAINT", "BASE-01", 1, None], ["AIR_BASIC", "P-CREW", "BASE-01", 1, None]]
    resource.extend([["AIR_BASIC", "P-MAINT", "BASE-02", 1, None], ["AIR_BASIC", "P-CREW", "BASE-02", 1, None]])
    stock = copy.deepcopy(rows(parent, "StockAllocation")[0])
    stock[2] = "BASE-02"
    rows(child, "StockAllocation").append(stock)
    depot_only = copy.deepcopy(child)
    forward_spare = copy.deepcopy(child)
    rows(forward_spare, "ProblemDescription")[0][0] = "F03.var02 two bases, one BASE-01 forward LRU"
    rows(forward_spare, "StockAllocation")[0][3] = 1
    return depot_only, forward_spare


def main() -> None:
    pair = dict(zip(("depot_only", "forward_spare"), build()))
    digests = {}
    for name, document in pair.items():
        raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{name}-input.json"
        if target.exists():
            assert target.read_bytes() == raw, f"frozen {name} source changed"
        else:
            target.write_bytes(raw)
        digests[name] = sha(raw)
    print(json.dumps({"parent": PARENT_SHA, "donor": A17_SHA, "inputs": digests}))


if __name__ == "__main__":
    main()
