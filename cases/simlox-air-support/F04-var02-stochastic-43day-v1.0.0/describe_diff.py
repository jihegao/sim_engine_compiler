"""Freeze the bounded F04 128-replication stochastic candidate delta."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, build


def main() -> None:
    old, new = json.loads(PARENT.read_bytes()), build()
    a = {t["name"]: t for t in old["model"]["tables"]}
    b = {t["name"]: t for t in new["model"]["tables"]}
    assert list(b) == list(a) + ["ReplicationResultControlSystem"]
    changed = [name for name in a if a[name] != b[name]]
    assert changed == ["ProblemDescription", "Control", "System", "Item", "MissionType"]
    cells = []
    for name in changed:
        before, after = a[name], b[name]
        assert before["columns"] == after["columns"]
        rows_before = before["instances"][0]["rows"]
        rows_after = after["instances"][0]["rows"]
        assert len(rows_before) == len(rows_after)
        for i, (row1, row2) in enumerate(zip(rows_before, rows_after), start=1):
            assert len(row1) == len(row2)
            for j, (v1, v2) in enumerate(zip(row1, row2)):
                if v1 != v2:
                    cells.append({"table": name, "row": i,
                                  "column": before["columns"][j]["name"],
                                  "from": v1, "to": v2})
    assert [(c["table"], c["column"]) for c in cells] == [
        ("ProblemDescription", "PDESC"), ("Control", "NREPS"), ("Control", "TCLEV"), ("System", "FRT"),
        ("Item", "FRT"), ("Item", "FRT"), ("MissionType", "MFF")]
    result = {"schema": "simlox-f04-stochastic-43day-diff/v1",
              "parent": "accepted F04.var01 deterministic 43-day fleet",
              "changed_cells": cells,
              "appended_table": b["ReplicationResultControlSystem"],
              "other_cells": "unchanged",
              "publication_state": "not_published"}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
