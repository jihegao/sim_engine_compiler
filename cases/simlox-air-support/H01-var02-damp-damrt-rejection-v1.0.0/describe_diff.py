"""Freeze the accepted rate source to simultaneous DAMP/DAMRT child delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, build


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
    parent_raw = PARENT.read_bytes()
    child_raw = (HERE / "simultaneous-input.json").read_bytes()
    if sha(parent_raw) != PARENT_SHA or child_raw != build():
        raise ValueError("source differs from builder")
    before, after = tables(parent_raw), tables(child_raw)
    if before.keys() != after.keys():
        raise ValueError("table topology differs")
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != ["MissionDamage", "ProblemDescription"]:
        raise ValueError(f"unexpected changed tables: {changed}")
    for name in changed:
        if before[name]["columns"] != after[name]["columns"]:
            raise ValueError(f"changed {name} columns")
    mission_before = before["MissionDamage"]["instances"][0]["rows"][0]
    mission_after = after["MissionDamage"]["instances"][0]["rows"][0]
    columns = [c["name"] for c in before["MissionDamage"]["columns"]]
    changed_fields = [field for i, field in enumerate(columns) if mission_before[i] != mission_after[i]]
    if changed_fields != ["DAMP"] or mission_before[columns.index("DAMP")] != 0 or mission_after[columns.index("DAMP")] != 1:
        raise ValueError(f"unexpected MissionDamage row delta: {changed_fields}")
    result = {
        "schema": "simlox-h01-var02-damp-damrt-rejection-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "child_sha256": sha(child_raw),
        "changed_tables": {name: {"before": before[name], "after": after[name]} for name in changed},
        "mission_damage_changed_fields": changed_fields,
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
    print(json.dumps({"changed": changed, "sha256": sha(raw)}))


if __name__ == "__main__":
    main()
