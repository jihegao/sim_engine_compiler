"""Freeze the REPF1 to REPF0 primary-LRU source delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT_SHA, PARENT


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
    control_raw = (HERE / "repairable-input.json").read_bytes()
    child_raw = (HERE / "discard-input.json").read_bytes()
    assert sha(parent_raw) == PARENT_SHA and control_raw == parent_raw
    before, after = tables(control_raw), tables(child_raw)
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(name for name in before if name in after and before[name] != after[name])
    assert not added and not removed and changed == ["DamageItem", "ProblemDescription"]
    assert before["DamageItem"]["instances"][0]["rows"][0][4] == 1
    assert after["DamageItem"]["instances"][0]["rows"][0][4] == 0
    result = {"schema": "simlox-h02-var03-repf-zero-exact-diff/v1",
              "parent_sha256": sha(parent_raw), "repairable_sha256": sha(control_raw),
              "discard_sha256": sha(child_raw), "added_tables": added,
              "removed_tables": removed,
              "changed_tables": {name: {"before": before[name], "after": after[name]}
                                 for name in changed},
              "unchanged_table_count": len(before) - len(changed)}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
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
