"""Build a paired group-owned START probe from accepted cross-unit and A17 sources."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A13-var02-cross-unit-start-v1.0.0" / "dependency-input.json"
STRUCTURE = ROOT / "A17-multi-unit-group-v1.0.0" / "native-input.json"
PARENT_SHA = "9bd317fdbd356c039c5db85dfb75077d78b1cb524cf52e845854e5754a30472a"
STRUCTURE_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"


def source(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted source changed: {path}")
    return json.loads(raw)


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def column(t: dict, name: str) -> int:
    return [c["name"] for c in t["columns"]].index(name)


def build(dependent: bool) -> dict:
    doc = copy.deepcopy(source(PARENT, PARENT_SHA))
    structural = source(STRUCTURE, STRUCTURE_SHA)
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "A13.var02 group-owned START dependency" if dependent else "A13.var02 group-owned no-row control"
    )
    # Copy accepted group membership with two explicit one-aircraft member units.
    for name in ("UnitGroup", "UnitGroupMember"):
        if any(t["name"] == name for t in doc["model"]["tables"]):
            raise ValueError(f"unexpected existing {name}")
        doc["model"]["tables"].append(copy.deepcopy(table(structural, name)))
    for name, old, new, changes in (
        ("Station", "BASE-02", "BASE-03", {"DESCR": "Third teaching base"}),
        ("Unit", "TEACH-UNIT-2", "TEACH-UNIT-3", {"DESCR": "Third one-aircraft teaching unit", "STID": "BASE-03"}),
        ("SystemDeployment", "TEACH-UNIT-2", "TEACH-UNIT-3", {}),
    ):
        t = table(doc, name)
        key = {"Station": "STID", "Unit": "UNID", "SystemDeployment": "USTID"}[name]
        rows = t["instances"][0]["rows"]
        selected = [r for r in rows if r[column(t, key)] == old]
        if len(selected) != 1:
            raise ValueError(f"expected one {name} donor row")
        row = copy.deepcopy(selected[0])
        row[column(t, key)] = new
        for field, value in changes.items():
            row[column(t, field)] = value
        rows.append(row)
    mission = table(doc, "MissionType")
    recon = next(r for r in mission["instances"][0]["rows"] if r[column(mission, "MTID")] == "RECON")
    recon[column(mission, "NOS")] = 2
    recon[column(mission, "MNOS")] = 2
    table(doc, "Operations")["instances"][0]["rows"] = [
        ["TEACH-GROUP", "RECON-SCHEDULE", None],
        ["TEACH-UNIT-3", "FOLLOW-SCHEDULE", None],
    ]
    dependence = table(doc, "MissionDependence")
    if dependent:
        row = dependence["instances"][0]["rows"][0]
        row[column(dependence, "DUNID")] = "TEACH-UNIT-3"
        row[column(dependence, "PUNID")] = "TEACH-GROUP"
    else:
        doc["model"]["tables"].remove(dependence)
    return doc


def main() -> None:
    for label, dependent in (("control", False), ("dependency", True)):
        raw = (json.dumps(build(dependent), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{label}-input.json"
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {label} input changed")
        path.write_bytes(raw)
        print(label, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
