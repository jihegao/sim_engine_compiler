"""Freeze ordinary INSPECT versus predefined <INSPECT> in serial preparation."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
VARIANTS = ("ordinary-control", "predefined-inspect")


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def put(t: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in t["columns"]].index(field)] = value


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published B02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = f"B05 ordinary versus built-in inspect preparation: {variant}"
    if variant == "predefined-inspect":
        breakdown = table(doc, "TaskBreakDown")
        put(breakdown, breakdown["instances"][0]["rows"][0], "SUTID", "<INSPECT>")
    return doc


def main() -> None:
    for variant in VARIANTS:
        data = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"frozen input differs: {variant}")
        path.write_bytes(data)
        print(variant, hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
