"""Freeze the accepted two-aircraft fixed control to DAMP=1 child source delta."""
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
    control_raw = (HERE / "control-input.json").read_bytes()
    damp_raw = (HERE / "damp-input.json").read_bytes()
    if control_raw != build("control") or damp_raw != build("damp"):
        raise ValueError("source differs from builder")
    before, after = tables(control_raw), tables(damp_raw)
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(name for name in before if name in after and before[name] != after[name])
    if added != ["DamageItem", "DamageType", "MissionDamage"] or removed or changed != ["ProblemDescription"]:
        raise ValueError(f"unexpected table delta: {added}, {removed}, {changed}")
    result = {
        "schema": "simlox-h01-var04-two-aircraft-damp-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "control_sha256": sha(control_raw),
        "damp_sha256": sha(damp_raw),
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
