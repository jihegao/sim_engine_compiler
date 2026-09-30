"""Build the A14.var03 regenerative-gap and fixed-precedent contrasts."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A14-continuous-end-abort-v1.0.1" / "control-input.json"
PARENT_SHA = "f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376"
TURNROUND_DONOR = HERE.parent / "B04-cross-midnight-turnround-v1.0.1" / "turnround-input.json"
TURNROUND_DONOR_SHA = "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"
DEPENDENCE_DONOR = HERE.parent / "A14-continuous-end-abort-v1.0.1" / "dependent-input.json"
DEPENDENCE_DONOR_SHA = "67484243a3b35395e21dcd6554a95c2637986086c4523d5e1ba99e2890d21de3"
VARIANTS = (
    "regenerative-control", "regenerative-zero", "regenerative-tolerant",
    "fixed-control", "fixed-tolerant",
)


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return matches[0]


def rows(tab: dict) -> list:
    return tab["instances"][0]["rows"]


def put(tab: dict, rec: list, key: str, old: object, new: object) -> None:
    index = [c["name"] for c in tab["columns"]].index(key)
    if rec[index] != old:
        raise ValueError(f"unexpected {tab['name']}.{key}: {rec[index]!r}")
    rec[index] = new


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    donor_raw = TURNROUND_DONOR.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published A14 parent fingerprint differs")
    if hashlib.sha256(donor_raw).hexdigest() != TURNROUND_DONOR_SHA:
        raise ValueError("published B04 turnround donor fingerprint differs")
    dep_raw = DEPENDENCE_DONOR.read_bytes()
    if hashlib.sha256(dep_raw).hexdigest() != DEPENDENCE_DONOR_SHA:
        raise ValueError("published A14 dependence donor fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    regenerative = variant.startswith("regenerative")
    put(table(doc, "ProblemDescription"), rows(table(doc, "ProblemDescription"))[0],
        "PDESC", "A14 paired continuous missions control", f"A14.var03 {variant}")
    mission = table(doc, "MissionType")
    support, execute = rows(mission)
    put(mission, support, "DESCR", "Two-hour continuous support", "Four-hour support sub-mission")
    put(mission, support, "DURN", 2.0, 4.0)
    put(mission, support, "MPAT", "CONTINUOUS", None)
    put(mission, support, "TFOUT", None, 0.25)
    put(mission, support, "TFRET", None, 0.25)
    put(mission, execute, "DESCR", "Four-hour continuous execution", "Six-and-quarter-hour continuous execution")
    put(mission, execute, "DURN", 4.0, 6.25)
    profile = table(doc, "OperationProfile")
    support_profile, execute_profile = rows(profile)
    if regenerative:
        put(profile, support_profile, "ITYPE", "SCHEDULED", "REGENERATIVE")
        put(profile, support_profile, "IQTY", 1, None)
        put(profile, support_profile, "IPER", 0, 6.5)
        put(profile, support_profile, "DTIM", 0.3333333333333333, None)
    donor = json.loads(donor_raw)
    turnround = copy.deepcopy(table(donor, "MissionTurnround"))
    turnround_row = rows(turnround)[0]
    put(turnround, turnround_row, "MTID", "BASIC-MISSION", "SUPPORT")
    put(turnround, turnround_row, "DURN", 1.0, 0.5)
    doc["model"]["tables"].append(turnround)
    if variant.endswith("zero") or variant.endswith("tolerant"):
        dep_donor = json.loads(dep_raw)
        dependence = copy.deepcopy(table(dep_donor, "MissionDependence"))
        dep_row = rows(dependence)[0]
        put(dependence, dep_row, "DTTOL", None, 0.0 if variant.endswith("zero") else 0.51)
        doc["model"]["tables"].append(dependence)
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{variant}-input.json"
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError(f"frozen input differs: {variant}")
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
