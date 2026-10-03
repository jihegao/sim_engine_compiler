"""Freeze the sole F02.var03 maintainer allocation edit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT_INPUT, PARENT_SHA


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted parent changed")
    left = json.loads(PARENT_INPUT.read_bytes())
    right_path = HERE / "no-conflict-input.json"
    right = json.loads(right_path.read_bytes())
    differences = []
    for lt, rt in zip(left["model"]["tables"], right["model"]["tables"]):
        if lt["name"] != rt["name"] or lt["columns"] != rt["columns"]:
            raise ValueError("table structure changed")
        lr, rr = lt["instances"][0]["rows"], rt["instances"][0]["rows"]
        if len(lr) != len(rr):
            raise ValueError("row count changed")
        for i, (a, b) in enumerate(zip(lr, rr)):
            for j, (av, bv) in enumerate(zip(a, b)):
                if av != bv:
                    differences.append({"table": lt["name"], "row": i, "column": lt["columns"][j]["name"], "before": av, "after": bv})
    expected = [{"table": "ResourceAllocation", "row": 0, "column": "RQTY", "before": 1, "after": 2}]
    if differences != expected:
        raise ValueError(f"not the frozen single-cell delta: {differences}")
    out = {"schema": "simlox-f02-var03-exact-parent-diff/v1", "parent_input_sha256": PARENT_SHA,
           "no_conflict_input_sha256": sha(right_path), "changed_cells": differences}
    raw = (json.dumps(out, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen diff changed")
    else:
        path.write_bytes(raw)
    print(json.dumps({"exact_diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_cells": differences}))


if __name__ == "__main__":
    main()
