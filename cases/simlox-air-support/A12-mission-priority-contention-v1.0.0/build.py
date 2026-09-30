"""Freeze a two-mission priority reversal from the accepted A11 typed minimum."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
PARENT_SHA = "4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213"
PREP_PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
PREP_PARENT_SHA = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
MISSIONS = ("BASIC-MISSION", "SECOND-MISSION")
SYSTEMS = ("TEACH-AIR-01", "TEACH-AIR-02")


def table(document: dict, name: str) -> dict:
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def put(t: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in t["columns"]].index(field)] = value


def source(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted source fingerprint changed: {path}")
    return json.loads(raw)


def build(variant: str) -> dict:
    if variant not in ("basic-high", "second-high"):
        raise ValueError(variant)
    doc = copy.deepcopy(source(PARENT, PARENT_SHA))
    prep = source(PREP_PARENT, PREP_PARENT_SHA)
    t = table(doc, "ProblemDescription")
    t["instances"][0]["rows"][0][0] = f"A12 simultaneous A+B missions, {variant} priority"

    t = table(doc, "MissionType")
    basic = t["instances"][0]["rows"][0]
    second = copy.deepcopy(basic)
    put(t, second, "MTID", MISSIONS[1])
    put(t, second, "DESCR", "Second competing two-hour A+B mission")
    put(t, basic, "PRI", 1 if variant == "basic-high" else 2)
    put(t, second, "PRI", 2 if variant == "basic-high" else 1)
    t["instances"][0]["rows"].append(second)

    t = table(doc, "OperationProfile")
    second = copy.deepcopy(t["instances"][0]["rows"][0])
    put(t, second, "SPRID", MISSIONS[1])
    t["instances"][0]["rows"].append(second)

    t = table(doc, "MissionSystem")
    old = list(t["instances"][0]["rows"])
    for row in old:
        other = copy.deepcopy(row)
        put(t, other, "MTID", MISSIONS[1])
        t["instances"][0]["rows"].append(other)

    source_prep = table(prep, "MissionPreparation")
    t = table(doc, "MissionPreparation")
    for mission in MISSIONS:
        for system in SYSTEMS:
            row = copy.deepcopy(source_prep["instances"][0]["rows"][0])
            put(t, row, "MTID", mission)
            put(t, row, "SID", system)
            t["instances"][0]["rows"].append(row)
    t = table(doc, "Tasks")
    t["instances"][0]["rows"].append(copy.deepcopy(table(prep, "Tasks")["instances"][0]["rows"][0]))
    return doc


def main() -> None:
    for variant in ("basic-high", "second-high"):
        data = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"frozen input differs: {path}")
        path.write_bytes(data)
        print(variant, hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
