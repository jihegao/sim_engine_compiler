"""Freeze RPROB zero/one from the accepted C06 both-zero-resource case."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C06-both-resource-zero-v1.0.0" / "both-zero-input.json"
PARENT_SHA256 = "05c6da90b5c8e509ea57132026d781822e1399d7693f469ec08c307bff9342cc"
VARIANTS = {"rprob-0": 0, "rprob-1": 1}


def build(variant: str) -> dict:
    probability = VARIANTS[variant]
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        f"C06 zero-resource probability endpoint; RPROB {probability}"
    )
    subtask_resource = tables["SubTaskResource"]["instances"][0]["rows"][0]
    assert subtask_resource[4] == 1
    subtask_resource[4] = probability
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
