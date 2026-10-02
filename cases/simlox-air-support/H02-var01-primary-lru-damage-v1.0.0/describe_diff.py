"""Freeze the accepted E01 to quiet control to LRU damage source deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import E01, E01_SHA, HERE


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    result = {item["name"]: item for item in items}
    if len(result) != len(items):
        raise ValueError("duplicate source table")
    return result


def delta(before: dict, after: dict) -> dict:
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(name for name in before if name in after and before[name] != after[name])
    return {"added_tables": {name: after[name] for name in added},
            "removed_tables": removed,
            "changed_tables": {name: {"before": before[name], "after": after[name]}
                               for name in changed},
            "unchanged_table_count": len(before) - len(changed)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = E01.read_bytes()
    control_raw = (HERE / "control-input.json").read_bytes()
    child_raw = (HERE / "lru-input.json").read_bytes()
    assert sha(parent_raw) == E01_SHA
    pc = delta(tables(parent_raw), tables(control_raw))
    cc = delta(tables(control_raw), tables(child_raw))
    assert not pc["added_tables"] and not pc["removed_tables"] and set(pc["changed_tables"]) == {
        "ProblemDescription", "System", "Item"}
    assert set(cc["added_tables"]) == {"DamageType", "MissionDamage", "DamageItem", "DamageReplacement"}
    assert not cc["removed_tables"] and set(cc["changed_tables"]) == {"ProblemDescription"}
    result = {"schema": "simlox-h02-var01-primary-lru-damage-exact-diff/v1",
              "parent_sha256": sha(parent_raw), "control_sha256": sha(control_raw),
              "lru_sha256": sha(child_raw), "parent_to_control": pc, "control_to_lru": cc}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"parent_to_control": sorted(pc["changed_tables"]),
                      "control_to_lru": sorted(cc["added_tables"]),
                      "sha256": sha(raw)}))


if __name__ == "__main__":
    main()
