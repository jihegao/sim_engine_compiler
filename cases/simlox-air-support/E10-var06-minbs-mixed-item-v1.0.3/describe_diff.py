"""Freeze exact second-IID addition and isolated MINBS arm contrast."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT_DIR, PARENT_SHA, build, sha

OUTPUT = HERE / "exact-diff.json"


def maps(doc: dict) -> dict:
    tables = doc["model"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def describe() -> dict:
    parent1 = maps(json.loads((PARENT_DIR / "native-input-minbs1.json").read_text(encoding="utf-8-sig")))
    parent2 = maps(json.loads((PARENT_DIR / "native-input-minbs2.json").read_text(encoding="utf-8-sig")))
    arm1, arm2 = (maps(json.loads(build(arm))) for arm in ("minbs1", "minbs2"))
    assert set(parent1) == set(parent2) == set(arm1) == set(arm2)
    assert sha(PARENT_DIR / "native-input-minbs1.json") == PARENT_SHA["minbs1"]
    assert sha(PARENT_DIR / "native-input-minbs2.json") == PARENT_SHA["minbs2"]
    changed = {"ProblemDescription", "Control", "Item", "ItemStructure", "ItemRepair", "StockAllocation", "System"}
    assert {name for name in parent1 if parent1[name] != arm1[name]} == changed
    assert {name for name in parent2 if parent2[name] != arm2[name]} == changed
    assert {name for name in arm1 if arm1[name] != arm2[name]} == {"ProblemDescription", "TransportPolicyProfile"}
    for name in changed - {"ProblemDescription", "System", "Control"}:
        old, new = parent1[name], arm1[name]
        assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
        old_rows, new_rows = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert new_rows[:len(old_rows)] == old_rows and len(new_rows) == len(old_rows) * 2
        assert arm1[name] == arm2[name]
    old_system, new_system = parent1["System"], arm1["System"]
    assert old_system["columns"] == new_system["columns"]
    frt_index = [c["name"] for c in old_system["columns"]].index("FRT")
    old_row = old_system["instances"][0]["rows"][0]
    new_row = new_system["instances"][0]["rows"][0]
    assert len(old_system["instances"]) == len(new_system["instances"]) == 1
    assert len(old_system["instances"][0]["rows"]) == len(new_system["instances"][0]["rows"]) == 1
    assert old_row[frt_index] == 3000000 and new_row[frt_index] == 6000000
    assert all(a == b for i, (a, b) in enumerate(zip(old_row, new_row)) if i != frt_index)
    assert arm1["System"] == arm2["System"]
    old_control, new_control = parent1["Control"], arm1["Control"]
    assert old_control["columns"] == new_control["columns"]
    seed_index = [c["name"] for c in old_control["columns"]].index("RSEED")
    old_row = old_control["instances"][0]["rows"][0]
    new_row = new_control["instances"][0]["rows"][0]
    assert len(old_control["instances"]) == len(new_control["instances"]) == 1
    assert len(old_control["instances"][0]["rows"]) == len(new_control["instances"][0]["rows"]) == 1
    assert old_row[seed_index] == "1" and new_row[seed_index] == "2"
    assert all(a == b for i, (a, b) in enumerate(zip(old_row, new_row)) if i != seed_index)
    assert arm1["Control"] == arm2["Control"]
    r1 = arm1["TransportPolicyProfile"]["instances"][0]["rows"]
    r2 = arm2["TransportPolicyProfile"]["instances"][0]["rows"]
    assert r1 == parent1["TransportPolicyProfile"]["instances"][0]["rows"]
    assert r2 == parent2["TransportPolicyProfile"]["instances"][0]["rows"]
    assert r1[0][6] == 1 and r2[0][6] == 2
    return {
        "schema": "simlox-e10-var06-minbs-mixed-item-exact-diff/v1",
        "parent_inputs_sha256": PARENT_SHA,
        "arm1_sha256": hashlib.sha256(build("minbs1")).hexdigest(),
        "arm2_sha256": hashlib.sha256(build("minbs2")).hexdigest(),
        "changed_tables_each_parent_to_child": sorted(changed),
        "changed_tables_between_child_arms": ["ProblemDescription", "TransportPolicyProfile"],
        "arm1_policy_row": r1[0],
        "arm2_policy_row": r2[0],
        "unchanged_tables_parent_to_child": len(parent1) - len(changed),
        "unchanged_tables_between_child_arms": len(arm1) - 2,
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
