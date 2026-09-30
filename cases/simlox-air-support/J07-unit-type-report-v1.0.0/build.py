"""Build two unit-owned, differently typed fixed missions from accepted A17."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
PARENT_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
OUTPUT = HERE / "native-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1
    return matches[0]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def names(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def replace(t: dict, index: int, **updates: object) -> None:
    for name, value in updates.items():
        rows(t)[index][names(t).index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    document = copy.deepcopy(json.loads(raw))
    model = document["model"]
    mission = table(model, "MissionType")
    assert len(rows(mission)) == 1
    second_mission = copy.deepcopy(rows(mission)[0])
    replace(mission, 0, MTID="MISSION-A", DESCR="Unit one fixed mission", NOS=1, MNOS=1)
    rows(mission).append(second_mission)
    replace(mission, 1, MTID="MISSION-B", DESCR="Unit two fixed mission", NOS=1, MNOS=1)

    profile = table(model, "OperationProfile")
    assert len(rows(profile)) == 1
    second_profile = copy.deepcopy(rows(profile)[0])
    replace(profile, 0, PRID="SCHEDULE-A", SPRID="MISSION-A")
    rows(profile).append(second_profile)
    replace(profile, 1, PRID="SCHEDULE-B", SPRID="MISSION-B")

    operations = table(model, "Operations")
    assert len(rows(operations)) == 1
    second_operations = copy.deepcopy(rows(operations)[0])
    replace(operations, 0, USTID="TEACH-UNIT", PRID="SCHEDULE-A")
    rows(operations).append(second_operations)
    replace(operations, 1, USTID="TEACH-UNIT-2", PRID="SCHEDULE-B")

    replace(table(model, "ProblemDescription"), 0, PDESC="J07 two unit-owned fixed missions of different types in one group")
    return document


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(json.dumps({"input_sha256": sha(raw), "parent_sha256": PARENT_SHA, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
