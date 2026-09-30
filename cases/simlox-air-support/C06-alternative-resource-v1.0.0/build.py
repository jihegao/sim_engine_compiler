"""Build C06 primary/alternative resource and ARTF candidates from C03."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
PARENT_SHA256 = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"
VARIANTS = {"primary-2-artf-2": (2, 2.0), "primary-0-artf-1": (0, 1.0), "primary-0-artf-2": (0, 2.0)}


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build(variant: str) -> dict:
    primary_capacity, artf = VARIANTS[variant]
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"C06 alternative prep resource; primary {primary_capacity}; ARTF {artf:g}"
    )
    table(doc, "MissionPreparation")["instances"][0]["rows"][0][3] = 1 / 3
    table(doc, "Tasks")["instances"][0]["rows"][0][1] = "Fixed 20-minute INSPECT preparation"
    table(doc, "TaskBreakDown")["instances"][0]["rows"][0][3] = 1 / 3
    subtask = table(doc, "SubTaskResource")["instances"][0]["rows"][0]
    subtask[5] = "P-ALT"
    subtask[6] = artf
    table(doc, "Resource")["instances"][0]["rows"].append(
        ["P-ALT", "Alternative preparation personnel", None, None, None, "SPECIAL", None, None]
    )
    allocation = table(doc, "ResourceAllocation")["instances"][0]["rows"]
    allocation[0][3] = primary_capacity
    allocation.append(["AIR_BASIC", "P-ALT", "BASE-01", 2, None])
    return doc


def main() -> None:
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {path}"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
