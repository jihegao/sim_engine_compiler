"""Verify the exact E12 QTY=2 to explicit two-base source delta."""
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
    expected = {"ProblemDescription", "Station", "StationStructure", "ItemStationStructure", "SystemRepair",
                "StockAllocation", "Unit", "SystemDeployment", "Operations"}
    changed = {name for name in before if before[name] != after[name]}
    assert changed == expected
    additions = []
    for name in sorted(changed):
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
        a, b = old["instances"][0]["rows"], new["instances"][0]["rows"]
        if name == "ProblemDescription":
            assert len(a) == len(b) == 1 and a[0][0] != b[0][0]
        elif name == "Station":
            assert len(a) == 2 and len(b) == 3 and a[0][:2] == b[0][:2] and a[0][2] == 2 and b[0][2] == 1 and b[2] == a[1]
            additions.append({"table": name, "index": 1, "columns": [c["name"] for c in old["columns"]], "row": b[1]})
        else:
            assert len(b) == len(a) + 1 and b[:-1] == a
            additions.append({"table": name, "index": len(a), "columns": [c["name"] for c in old["columns"]], "row": b[-1]})
    assert len(additions) == 8
    return {"schema": "simlox-e12-var01-explicit-two-bases-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": sorted(changed),
            "unchanged_parent_tables": len(before) - len(changed),
            "description_before": before["ProblemDescription"]["instances"][0]["rows"][0][0],
            "description_after": after["ProblemDescription"]["instances"][0]["rows"][0][0],
            "base01_qty_before": 2, "base01_qty_after": 1,
            "added_rows": additions}


if __name__ == "__main__":
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode()
    if sys.argv[1:] == ["--write"]:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: describe_diff.py [--write]")
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())
