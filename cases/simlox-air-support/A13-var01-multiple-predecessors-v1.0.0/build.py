"""Build a three-way A13 START predecessor probe from accepted A13 input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
VARIANTS = ("control", "single", "multiple")


def tab(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def set_field(table: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in table["columns"]].index(field)] = value


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A13 source changed")
    doc = copy.deepcopy(json.loads(raw))
    tab(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"A13.var01 three-aircraft early/late START precedent {variant}"
    )
    t = tab(doc, "SystemDeployment")
    set_field(t, t["instances"][0]["rows"][0], "QTYPS", 3)
    t = tab(doc, "Unit")
    set_field(t, t["instances"][0]["rows"][0], "DESCR", "Three-aircraft two-predecessor unit")
    t = tab(doc, "MissionType")
    original_recon, follow = t["instances"][0]["rows"]
    early = copy.deepcopy(original_recon)
    late = copy.deepcopy(original_recon)
    set_field(t, early, "MTID", "EARLY")
    set_field(t, early, "DESCR", "One-hour fixed predecessor returning at 9")
    set_field(t, early, "DURN", 1.0)
    set_field(t, early, "MSUCPT", 1.0)
    set_field(t, late, "MTID", "LATE")
    set_field(t, late, "DESCR", "Four-hour fixed predecessor returning at 12")
    set_field(t, late, "DURN", 4.0)
    set_field(t, late, "MSUCPT", 1.0)
    set_field(t, follow, "DESCR", "Two-hour fixed dependent")
    t["instances"][0]["rows"] = [early, late, follow]
    t = tab(doc, "OperationProfile")
    original_recon, follow = t["instances"][0]["rows"]
    early = copy.deepcopy(original_recon)
    late = copy.deepcopy(original_recon)
    set_field(t, early, "SPRID", "EARLY")
    set_field(t, late, "SPRID", "LATE")
    set_field(t, follow, "SPRID", "FOLLOW")
    t["instances"][0]["rows"] = [early, late, follow]
    t = tab(doc, "MissionDependence")
    original = t["instances"][0]["rows"][0]
    early_row = copy.deepcopy(original)
    late_row = copy.deepcopy(original)
    set_field(t, early_row, "PMTID", "EARLY")
    set_field(t, late_row, "PMTID", "LATE")
    t["instances"][0]["rows"] = {
        "control": [], "single": [early_row], "multiple": [early_row, late_row]
    }[variant]
    if variant == "control":
        doc["model"]["tables"].remove(t)
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{variant}-input.json"
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError(f"frozen {variant} input changed")
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
