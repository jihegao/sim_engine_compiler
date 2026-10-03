"""Freeze and verify the E03-to-E13 diagnostic input delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"
CHANGED = ["Control", "Item", "ItemRepair", "ItemStructure", "ProblemDescription", "StockAllocation", "System"]


def describe() -> dict:
    old = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    new = json.loads(build())
    before = {t["name"]: t for t in old["model"]["tables"]}
    after = {t["name"]: t for t in new["model"]["tables"]}
    assert len(before) == len(after) == 31 and set(before) == set(after)
    changed = sorted(n for n in before if before[n] != after[n])
    assert changed == CHANGED
    modified, added = [], []
    for name in changed:
        a, b = before[name], after[name]
        assert a["columns"] == b["columns"] and len(a["instances"]) == len(b["instances"]) == 1
        cols = [c["name"] for c in a["columns"]]
        prior, child = a["instances"][0]["rows"], b["instances"][0]["rows"]
        assert len(prior) <= len(child)
        for ri, (ar, br) in enumerate(zip(prior, child)):
            for ci, (x, y) in enumerate(zip(ar, br)):
                if x != y:
                    modified.append({"table": name, "row": ri, "column": cols[ci], "before": x, "after": y})
        for ri in range(len(prior), len(child)):
            added.append({"table": name, "row": ri, "values": dict(zip(cols, child[ri]))})
    assert len(modified) == 6 and len(added) == 4
    assert {(x["table"], x["column"]) for x in modified} == {
        ("Control", "ENROB"), ("ProblemDescription", "PDESC"),
        ("System", "FRT"), ("StockAllocation", "STSIZ"), ("Item", "FRT"),
        ("ItemRepair", "DIRPT")
    }
    return {"schema": "simlox-e13-var01-two-item-no-robbing-control-exact-diff/v1",
            "parent_sha256": PARENT_SHA, "source_sha256": hashlib.sha256(build()).hexdigest(),
            "changed_tables": changed, "unchanged_parent_tables": 31 - len(changed),
            "modified_cells": modified, "added_rows": added}


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
