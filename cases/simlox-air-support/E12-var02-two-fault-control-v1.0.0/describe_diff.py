"""Verify the exact longer-mission control delta from E12.var01."""
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
    changed = sorted(name for name in before if before[name] != after[name])
    assert changed == ["MissionType", "ProblemDescription"]
    changes = []
    for name in changed:
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
        names = [c["name"] for c in old["columns"]]
        for ri, (a, b) in enumerate(zip(old["instances"][0]["rows"], new["instances"][0]["rows"])):
            for ci, (x, y) in enumerate(zip(a, b)):
                if x != y:
                    changes.append({"table": name, "row": ri, "column": names[ci], "before": x, "after": y})
    assert [(x["table"], x["column"], x["before"], x["after"]) for x in changes] == [
        ("MissionType", "DURN", 2.0, 3.5),
        ("ProblemDescription", "PDESC", "E12.var01 two explicit bases with one unit, aircraft and local spare per base", "E12.var02 individual SystemRepair control with 3.5-hour missions at two bases"),
    ]
    return {"schema": "simlox-e12-var02-two-fault-control-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": changed,
            "unchanged_parent_tables": len(before) - len(changed), "changes": changes}


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
