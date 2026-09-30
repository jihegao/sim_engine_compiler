"""Freeze single, formation, and later three-aircraft denied-demand inputs."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SINGLE = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
FORMATION = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
SINGLE_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
FORMATION_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build() -> dict[str, bytes]:
    single_raw = SINGLE.read_bytes()
    formation_raw = FORMATION.read_bytes()
    assert hashlib.sha256(single_raw).hexdigest() == SINGLE_SHA
    assert hashlib.sha256(formation_raw).hexdigest() == FORMATION_SHA
    formation = json.loads(formation_raw)
    assert table(formation, "SystemDeployment")["instances"][0]["rows"] == [
        ["TEACH-AIR-01", "TEACH-UNIT", 2, 1, None, None, None]
    ]
    mission = table(formation, "MissionType")["instances"][0]["rows"][0]
    assert mission[:10] == ["BASIC-MISSION", "Two-hour generic mission", 2, 2, None, 2.0, None, 1, .25, .25]
    assert table(formation, "OperationProfile")["instances"][0]["rows"] == [
        ["BASIC-SCHEDULE", "BASIC-MISSION", 8.0, "SCHEDULED", 1, None, 0, None,
         0.3333333333333333, None, None, None]
    ]
    denied = copy.deepcopy(formation)
    table(denied, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "J07 two-aircraft wave at 8 plus unfilled three-aircraft demand at 12"
    )
    extra_mission = copy.deepcopy(mission)
    extra_mission[0:4] = ["THREE-AIR-DEMAND", "Two-hour demand requiring three aircraft", 3, 3]
    table(denied, "MissionType")["instances"][0]["rows"].append(extra_mission)
    extra_order = copy.deepcopy(table(denied, "OperationProfile")["instances"][0]["rows"][0])
    extra_order[1] = "THREE-AIR-DEMAND"
    extra_order[2] = 12.0
    table(denied, "OperationProfile")["instances"][0]["rows"].append(extra_order)
    return {
        "single-control": single_raw,
        "formation-control": formation_raw,
        "denied-demand": (json.dumps(denied, ensure_ascii=False, indent=2) + "\n").encode(),
    }


def main() -> None:
    for name, raw in build().items():
        path = HERE / f"{name}-input.json"
        if path.exists():
            assert path.read_bytes() == raw, f"frozen {name} differs"
        else:
            path.write_bytes(raw)
        print(name, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
