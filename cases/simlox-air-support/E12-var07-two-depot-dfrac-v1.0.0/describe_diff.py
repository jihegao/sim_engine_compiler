"""Verify exact symmetric two-depot DFRAC graph delta."""
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
    assert changed == ["ItemStationStructure", "ProblemDescription", "Station", "StationStructure", "StockAllocation"]
    modifications, additions = [], []
    for name in changed:
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
        names = [c["name"] for c in old["columns"]]
        a, b = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert len(a) <= len(b)
        for ri, (ar, br) in enumerate(zip(a, b)):
            for ci, (x, y) in enumerate(zip(ar, br)):
                if x != y:
                    modifications.append({"table": name, "row": ri, "column": names[ci], "before": x, "after": y})
        for ri in range(len(a), len(b)):
            additions.append({"table": name, "row": ri, "values": dict(zip(names, b[ri]))})
    assert len(modifications) == 5 and len(additions) == 6
    assert sorted((x["table"], x["column"]) for x in modifications) == sorted(
        [("ProblemDescription", "PDESC")] + [(n, "DFRAC") for n in ("StationStructure", "ItemStationStructure") for _ in range(2)]
    )
    assert {x["table"] for x in additions} == {"Station", "StationStructure", "ItemStationStructure", "StockAllocation"}
    return {"schema": "simlox-e12-var07-two-depot-dfrac-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": changed,
            "unchanged_parent_tables": len(before) - len(changed), "modified_cells": modifications, "added_rows": additions}


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
