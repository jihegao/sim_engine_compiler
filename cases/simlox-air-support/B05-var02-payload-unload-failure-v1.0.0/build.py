"""Freeze failed payloaded mission with ordinary versus built-in unloading."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B05-var02-payload-unload-success-v1.0.0" / "ordinary-control-input.json"
PARENT_SHA = "21bd66e3ba54e22fb5d7c7c9b612892faf2999cb873f7dd34483e5880a607c9a"
D01 = HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
D01_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
VARIANTS = ("ordinary-control", "unloading")


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def put(t: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in t["columns"]].index(field)] = value


def load(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"accepted source fingerprint differs: {path}")
    return json.loads(raw)


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    doc = copy.deepcopy(load(PARENT, PARENT_SHA))
    d01 = load(D01, D01_SHA)
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = f"B05 failed payloaded mission and turnround: {variant}"
    system = table(doc, "System")
    put(system, system["instances"][0]["rows"][0], "FRT", 300000)
    repair = table(doc, "SystemRepair")
    accepted_repair = table(d01, "SystemRepair")
    repair["columns"] = copy.deepcopy(accepted_repair["columns"])
    repair["instances"] = copy.deepcopy(accepted_repair["instances"])
    if variant == "unloading":
        breakdown = table(doc, "TaskBreakDown")
        turn = next(row for row in breakdown["instances"][0]["rows"] if row[0] == "TURN-FIXED")
        put(breakdown, turn, "SUTID", "<UNLOADING>")
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
