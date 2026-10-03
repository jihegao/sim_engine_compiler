"""Verify the complete E07 to E12 symmetric-base source delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(before) == set(after)
    changes = []
    for name in sorted(before):
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
        columns = [c["name"] for c in old["columns"]]
        old_rows, new_rows = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert len(old_rows) == len(new_rows)
        for ri, (a, b) in enumerate(zip(old_rows, new_rows)):
            for ci, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    changes.append({"table": name, "row": ri, "column": columns[ci], "before": x, "after": y})
    assert [(c["table"], c["row"], c["column"], c["before"], c["after"]) for c in changes] == [
        ("ProblemDescription", 0, "PDESC", "E07 item-specific FAST route overrides general two-hour transport with one-hour down and three-hour up", "E12 two symmetric BASE-01 instances with one local spare and one aircraft each"),
        ("Station", 0, "QTY", 1, 2),
        ("StockAllocation", 0, "STSIZ", 0, 1),
    ]
    return {"schema": "simlox-e12-symmetric-bases-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": ["ProblemDescription", "Station", "StockAllocation"],
            "unchanged_parent_tables": len(before) - 3, "changes": changes}


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
