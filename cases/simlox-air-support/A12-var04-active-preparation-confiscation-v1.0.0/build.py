"""Freeze A12 later-call preparation-confiscation priority pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A12-mission-priority-contention-v1.0.0" / "basic-high-input.json"
PARENT_SHA = "300f3129b1f5d78018ad00875b545ffc1d7619dde5c3086c7a8bf0abb145094a"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def set_field(t: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in t["columns"]].index(field)] = value


def build(variant: str) -> dict:
    if variant not in ("early-high", "late-high"):
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published A12 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = f"A12 active preparation transfer candidate: {variant}"
    mission = table(doc, "MissionType")
    for row in mission["instances"][0]["rows"]:
        mid = row[0]
        priority = (1 if mid == "BASIC-MISSION" else 2) if variant == "early-high" else (2 if mid == "BASIC-MISSION" else 1)
        set_field(mission, row, "PRI", priority)
    profile = table(doc, "OperationProfile")
    second = next(row for row in profile["instances"][0]["rows"] if row[1] == "SECOND-MISSION")
    set_field(profile, second, "STIM", 8.25)
    return doc


def main() -> None:
    for variant in ("early-high", "late-high"):
        data = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"frozen input differs: {path}")
        path.write_bytes(data)
        print(variant, hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
