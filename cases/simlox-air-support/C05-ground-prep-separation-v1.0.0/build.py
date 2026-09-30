"""Build C05 ground-preparation versus mission-held resource candidates."""

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


def build(ground_capacity: int) -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"C05 distinct ground preparation resource capacity {ground_capacity}"
    )
    table(doc, "Resource")["instances"][0]["rows"].append(
        ["GROUND-TECH", "Ground preparation technician", None, None, None, "SPECIAL", None, None]
    )
    table(doc, "ResourceAllocation")["instances"][0]["rows"].append(
        ["AIR_BASIC", "GROUND-TECH", "BASE-01", ground_capacity, None]
    )
    table(doc, "MissionPreparation")["instances"][0]["rows"] = [
        ["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 0.5, "GROUND-PREP", None, None]
    ]
    table(doc, "Tasks")["instances"][0]["rows"] = [
        ["GROUND-PREP", "Half-hour ground preparation", None, None, None]
    ]
    table(doc, "TaskResource")["instances"][0]["rows"] = [
        ["GROUND-PREP", "GROUND-TECH", 1, 1, None, None, None, None]
    ]
    return doc


def main() -> None:
    for capacity in (2, 0):
        path = HERE / f"ground-{capacity}-input.json"
        raw = (json.dumps(build(capacity), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen input differs: {path}"
        else:
            path.write_bytes(raw)
        print(capacity, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
