"""Freeze twelve RPROB=0.5 native inputs with distinct explicit seeds."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C06-rprob-endpoints-v1.0.0" / "rprob-1-input.json"
PARENT_SHA256 = "0e548e167a48aed7e76dfeec5b0fbdfbb817f41bc3c88e0b1e246396ab218fa4"
VARIANTS = {f"seed-{seed:02d}": seed for seed in range(1, 13)}


def build(variant: str) -> dict:
    seed = VARIANTS[variant]
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        f"C06 intermediate probability resource demand; RPROB 0.5; seed {seed}"
    )
    resource = tables["SubTaskResource"]["instances"][0]["rows"][0]
    assert resource[4] == 1
    resource[4] = 0.5
    control = tables["Control"]["instances"][0]["rows"][0]
    assert str(control[2]) == "1"
    control[2] = str(seed)
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
