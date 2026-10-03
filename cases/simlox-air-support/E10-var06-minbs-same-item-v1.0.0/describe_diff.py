"""Freeze the parent-to-two-demand model and isolated MINBS arm delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT, PARENT_SHA, SUPPORT_SHA, build, sha

OUTPUT = HERE / "exact-diff.json"


def maps(doc: dict) -> dict:
    tables = doc["model"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def describe() -> dict:
    assert sha(PARENT) == PARENT_SHA
    parent = maps(json.loads(PARENT.read_text(encoding="utf-8-sig")))
    arm1 = maps(json.loads(build(1)))
    arm2 = maps(json.loads(build(2)))
    assert set(parent) == set(arm1) == set(arm2)
    changed_parent = {name for name in parent if parent[name] != arm1[name]}
    assert changed_parent == {"ProblemDescription", "System", "Item", "SystemDeployment", "OperationProfile", "StockAllocation"}
    assert {name for name in arm1 if arm1[name] != arm2[name]} == {"ProblemDescription", "TransportPolicyProfile"}
    p1, p2 = arm1["TransportPolicyProfile"], arm2["TransportPolicyProfile"]
    assert p1["columns"] == p2["columns"] and len(p1["instances"]) == len(p2["instances"]) == 1
    r1, r2 = p1["instances"][0]["rows"], p2["instances"][0]["rows"]
    assert r1 == [["DOWN-POLICY", "ONDEM", 0.0, 1, 0.0, 36.0, 1, 2.0, None, None]]
    assert r2 == [["DOWN-POLICY", "ONDEM", 0.0, 1, 0.0, 36.0, 2, 2.0, None, None]]
    for name in arm1.keys() - {"ProblemDescription", "TransportPolicyProfile"}:
        assert arm1[name] == arm2[name]
    return {
        "schema": "simlox-e10-var06-minbs-same-item-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "support_e03_sha256": SUPPORT_SHA,
        "arm1_sha256": hashlib.sha256(build(1)).hexdigest(),
        "arm2_sha256": hashlib.sha256(build(2)).hexdigest(),
        "changed_tables_parent_to_arm1": sorted(changed_parent),
        "changed_tables_arm1_to_arm2": ["ProblemDescription", "TransportPolicyProfile"],
        "arm1_policy_row": r1[0],
        "arm2_policy_row": r2[0],
        "unchanged_tables_parent_to_arm1": len(parent) - len(changed_parent),
        "unchanged_tables_between_arms": len(arm1) - 2,
    }


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
