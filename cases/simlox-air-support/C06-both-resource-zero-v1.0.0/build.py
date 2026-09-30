"""Freeze the C06 no-primary/no-alternative boundary from the accepted C06 input."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C06-alternative-resource-v1.0.0" / "primary-0-artf-2-input.json"
PARENT_SHA256 = "42aeabcf2f7ca79efc568c515bfd5989715cdc0270f59acaad3bfe46c974bd1f"


def build() -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        "C06 alternative preparation resource; primary 0; alternative 0; ARTF 2"
    )
    allocations = tables["ResourceAllocation"]["instances"][0]["rows"]
    alternative = next(row for row in allocations if row[1] == "P-ALT")
    assert alternative[3] == 2
    alternative[3] = 0
    return doc


def main() -> None:
    path = HERE / "both-zero-input.json"
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw, f"frozen source differs: {path}"
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
