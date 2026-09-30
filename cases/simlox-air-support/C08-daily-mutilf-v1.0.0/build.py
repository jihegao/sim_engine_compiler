"""Derive four no-shift daily-utilization controls from accepted C07.var04."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
PARENT_SHA = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"
VARIANTS = ("no-shift-control", "zero-budget", "finite-budget", "station-override")


def build(variant: str) -> dict:
    assert variant in VARIANTS
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert description == ["C07 two equivalent crew shifts via explicit profile; DRAOS=N"]
    description[0] = f"C08 daily MUTILF {variant} without active shift; DRAOS=N"
    station = tables["ResourceStationData"]["instances"][0]["rows"][0]
    resource = tables["Resource"]["instances"][0]["rows"][0]
    assert station == ["P-CREW", "BASE-01", None, None, None, None, None, None, None, "CREW-DAY", None]
    assert resource == ["P-CREW", "Crew A personnel", None, None, None, "SPECIAL", None, None]
    station[9] = None  # Disable the reference to shift profile; retain inert source tables for exact lineage.
    if variant == "zero-budget":
        resource[6] = 0.0
    elif variant in ("finite-budget", "station-override"):
        resource[6] = 0.03125  # 0.75 hour per crew per 24-hour day; two-crew pool budget 1.5 hours.
    if variant == "station-override":
        station[4] = 1.0
    return doc


def main() -> None:
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {variant}"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
