"""Verify exact four-cell group intersection delta from accepted E12.var03."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(before) == set(after) and len(before) == 32
    changed = sorted(n for n in before if before[n] != after[n])
    assert changed == ["Item", "ItemRepair", "ProblemDescription", "Station"]
    cells = []
    for name in changed:
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
        names = [c["name"] for c in old["columns"]]
        a, b = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert len(a) == len(b)
        for ri, (ar, br) in enumerate(zip(a, b)):
            for ci, (x, y) in enumerate(zip(ar, br)):
                if x != y:
                    cells.append({"table": name, "row": ri, "column": names[ci], "before": x, "after": y})
    assert [(c["table"], c["row"], c["column"], c["before"], c["after"]) for c in cells] == [
        ("Item", 0, "GIID", None, "LRU-GRP"),
        ("ItemRepair", 0, "IID", "TEACH-LRU-01", "LRU-GRP"),
        ("ItemRepair", 0, "STID", "DEPOT-01", "DEPOT-GRP"),
        ("ProblemDescription", 0, "PDESC", "E12.var03 BASE-02 one-hour individual SystemRepair override of BASE-GRP half-hour default", "E12.var04 LRU-GRP by DEPOT-GRP ItemRepair intersection with BASE-02 SystemRepair override"),
        ("Station", 2, "GSTID", None, "DEPOT-GRP"),
    ]
    return {"schema": "simlox-e12-var04-item-station-group-repair-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": changed,
            "unchanged_parent_tables": len(before) - len(changed), "changed_cells": cells}


if __name__ == "__main__":
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if sys.argv[1:] == ["--write"]:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: describe_diff.py [--write]")
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())
