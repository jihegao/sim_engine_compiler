"""Freeze the accepted attrition to airframe direct-repair source delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT_SHA, build


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    result = {item["name"]: item for item in items}
    if len(result) != len(items):
        raise ValueError("duplicate source table")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    control_raw = (HERE / "attrition-input.json").read_bytes()
    child_raw = (HERE / "system-input.json").read_bytes()
    if control_raw != build("attrition") or child_raw != build("system"):
        raise ValueError("source differs from builder")
    before, after = tables(control_raw), tables(child_raw)
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(name for name in before if name in after and before[name] != after[name])
    if added != ["DamageRepair"] or removed or changed != ["DamageItem", "ProblemDescription"]:
        raise ValueError(f"unexpected table delta: {added}, {removed}, {changed}")
    result = {
        "schema": "simlox-h02-var01-system-direct-repair-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "attrition_sha256": sha(control_raw),
        "system_sha256": sha(child_raw),
        "added_tables": {name: after[name] for name in added},
        "removed_tables": removed,
        "changed_tables": {name: {"before": before[name], "after": after[name]} for name in changed},
        "unchanged_table_count": len(before) - len(changed),
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"added": added, "changed": changed, "sha256": sha(raw)}))


if __name__ == "__main__":
    main()
