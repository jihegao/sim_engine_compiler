"""Verify the complete group-owned operations source delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert len(before) == 32 and len(after) == 34
    assert set(after) - set(before) == {"UnitGroup", "UnitGroupMember"} and set(before) <= set(after)
    changed = sorted(n for n in before if before[n] != after[n])
    assert changed == ["OperationProfile", "Operations", "ProblemDescription"]
    assert all(before[n] == after[n] for n in set(before) - set(changed))
    op_old = before["Operations"]["instances"][0]["rows"]
    op_new = after["Operations"]["instances"][0]["rows"]
    assert len(op_old) == 2 and op_new == [["TEACH-GROUP", "BASIC-SCHEDULE", None]]
    profile_old = before["OperationProfile"]["instances"][0]["rows"]
    profile_new = after["OperationProfile"]["instances"][0]["rows"]
    modifications = [
        {"table": "ProblemDescription", "row": 0, "column": "PDESC", "before": before["ProblemDescription"]["instances"][0]["rows"][0][0], "after": after["ProblemDescription"]["instances"][0]["rows"][0][0]},
        {"table": "Operations", "row": 0, "column": "USTID", "before": op_old[0][0], "after": op_new[0][0]},
    ]
    for i, (old, new) in enumerate(zip(profile_old, profile_new)):
        assert len(old) == len(new) and [(j, a, b) for j, (a, b) in enumerate(zip(old, new)) if a != b] == [(4, 1, 2)]
        modifications.append({"table": "OperationProfile", "row": i, "column": "IQTY", "before": 1, "after": 2})
    return {
        "schema": "simlox-e12-var08-unit-group-expansion-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "source_sha256": hashlib.sha256(build()).hexdigest(),
        "changed_existing_tables": changed,
        "unchanged_parent_tables": len(before) - len(changed),
        "added_tables": {n: after[n] for n in ("UnitGroup", "UnitGroupMember")},
        "modified_cells": modifications,
        "removed_rows": [{"table": "Operations", "row": 1, "values": op_old[1]}],
    }


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
