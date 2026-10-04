"""Freeze the exact symmetric two-unit station-location comparison."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, build


def main() -> None:
    parent = json.loads(PARENT.read_bytes())
    base1, base2 = build()
    before = {t["name"]: t for t in parent["model"]["tables"]}
    left = {t["name"]: t for t in base1["model"]["tables"]}
    right = {t["name"]: t for t in base2["model"]["tables"]}
    assert before.keys() == left.keys() == right.keys() and len(before) == 32
    parent_delta = [name for name in before if before[name] != left[name]]
    pair_delta = [name for name in left if left[name] != right[name]]
    assert parent_delta == ["ProblemDescription"]
    assert pair_delta == ["ProblemDescription", "Unit", "MissionPreparation", "MissionTurnround"]
    cells = []
    for name in pair_delta:
        a, b = left[name], right[name]
        assert a["columns"] == b["columns"] and len(a["instances"]) == len(b["instances"]) == 1
        ar, br = a["instances"][0]["rows"], b["instances"][0]["rows"]
        assert len(ar) == len(br)
        for row_num, (ra, rb) in enumerate(zip(ar, br), 1):
            assert len(ra) == len(rb) == len(a["columns"])
            for col_num, (va, vb) in enumerate(zip(ra, rb)):
                if va != vb:
                    cells.append({"table": name, "row": row_num, "key": ra[0], "column": a["columns"][col_num]["name"], "risk_base1": va, "risk_base2": vb})
    assert len(cells) == 9 and sum(c["column"] == "STID" for c in cells) == 8
    assert all(c["column"] in ("PDESC", "STID") for c in cells)
    result = {"schema": "simlox-f03-demand-location-diff/v1", "parent_changed_tables": parent_delta,
              "pair_changed_tables": pair_delta, "pair_changed_cells": cells,
              "business_delta": "Move TEACH-UNIT with two risk aircraft BASE-01 to BASE-02 and TEACH-UNIT-2 with one aircraft BASE-02 to BASE-01, with matching mission preparation/turnround location rows; all stock, resources, routes, repair/PM and schedules fixed."}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
