"""Build a paired cross-unit START probe from accepted A13 and A17 sources."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
A13 = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
A17 = ROOT / "A17-multi-unit-group-v1.0.0" / "native-input.json"
A13_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
A17_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def col(table: dict, name: str) -> int:
    return [c["name"] for c in table["columns"]].index(name)


def source(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted source changed: {path}")
    return json.loads(raw)


def build(dependent: bool) -> dict:
    doc = copy.deepcopy(source(A13, A13_SHA))
    two_unit = source(A17, A17_SHA)
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "A13.var02 two-unit START dependency" if dependent else "A13.var02 two-unit no-row control"
    )
    for name in ("Station", "SystemDeployment", "Unit"):
        dst = table(doc, name)
        ref = table(two_unit, name)
        if dst["columns"] != ref["columns"]:
            raise ValueError(f"A13/A17 {name} columns differ")
        dst["instances"][0]["rows"] = copy.deepcopy(ref["instances"][0]["rows"])
    # A17's two-unit geometry already provides one deployed aircraft per unit.
    t = table(doc, "OperationProfile")
    rows = t["instances"][0]["rows"]
    rows[0][col(t, "PRID")] = "RECON-SCHEDULE"
    rows[1][col(t, "PRID")] = "FOLLOW-SCHEDULE"
    t = table(doc, "Operations")
    t["instances"][0]["rows"] = [
        ["TEACH-UNIT", "RECON-SCHEDULE", None],
        ["TEACH-UNIT-2", "FOLLOW-SCHEDULE", None],
    ]
    t = table(doc, "MissionDependence")
    if dependent:
        row = t["instances"][0]["rows"][0]
        row[col(t, "DUNID")] = "TEACH-UNIT-2"
        row[col(t, "PUNID")] = "TEACH-UNIT"
    else:
        doc["model"]["tables"].remove(t)
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
