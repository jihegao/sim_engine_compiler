"""Build frozen C05.var02 all-resource-types-per-aircraft candidates."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C05-mission-resource-v1.0.0" / "capacity-2-input.json"
PARENT_SHA256 = "d2ea6e874eff82f1e50f271051010985c28adfba7aab94d2a0a0b343b989e865"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build(radio_capacity: int) -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "Resource")["instances"][0]["rows"].append(
        ["MISSION-RADIO", "Distinct mission radio resource", None, None, None, "SPECIAL", None, None]
    )
    table(doc, "ResourceAllocation")["instances"][0]["rows"].append(
        ["AIR_BASIC", "MISSION-RADIO", "BASE-01", radio_capacity, None]
    )
    table(doc, "MissionResource")["instances"][0]["rows"].append(
        ["BASIC-MISSION", "TEACH-AIR-01", "MISSION-RADIO", 1, None]
    )
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"C05.var02 two mission resource types; radio capacity {radio_capacity}"
    )
    return doc


def main() -> None:
    for capacity in (2, 0):
        path = HERE / f"radio-{capacity}-input.json"
        raw = (json.dumps(build(capacity), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {path}"
        else:
            path.write_bytes(raw)
        print(capacity, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
