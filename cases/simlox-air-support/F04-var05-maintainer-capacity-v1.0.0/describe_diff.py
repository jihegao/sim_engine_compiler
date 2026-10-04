"""Freeze the two-cell maintainer-capacity source delta."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, build


def main() -> None:
    old, new = json.loads(PARENT.read_bytes()), build()
    a = {t["name"]: t for t in old["model"]["tables"]}
    b = {t["name"]: t for t in new["model"]["tables"]}
    assert list(a) == list(b)
    changed = [name for name in a if a[name] != b[name]]
    assert changed == ["ProblemDescription", "ResourceAllocation"]
    cells = []
    for name in changed:
        before, after = a[name], b[name]
        assert before["columns"] == after["columns"]
        first = before["instances"][0]["rows"]
        second = after["instances"][0]["rows"]
        assert len(first) == len(second)
        for i, (row1, row2) in enumerate(zip(first, second), start=1):
            assert len(row1) == len(row2)
            for j, (v1, v2) in enumerate(zip(row1, row2)):
                if v1 != v2:
                    cells.append({"table": name, "row": i,
                                  "column": before["columns"][j]["name"],
                                  "from": v1, "to": v2})
    assert [(c["table"], c["row"], c["column"]) for c in cells] == [
        ("ProblemDescription", 1, "PDESC"),
        ("ResourceAllocation", 1, "RQTY")]
    result = {"schema": "simlox-f04-maintainer-capacity-diff/v1",
              "parent": "accepted F04.var01 deterministic 43-day simulation",
              "changed_cells": cells, "other_cells": "unchanged",
              "publication_state": "not_published"}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
