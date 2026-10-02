"""Freeze the precise no-task-reference source delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    out = {item["name"]: item for item in items}
    assert len(out) == len(items)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    reference_raw = (HERE / "referenced-input.json").read_bytes()
    unref_raw = (HERE / "unreferenced-input.json").read_bytes()
    assert sha(parent_raw) == PARENT_SHA and parent_raw == reference_raw
    before, after = tables(reference_raw), tables(unref_raw)
    assert before.keys() == after.keys()
    changed = {name: {"before": before[name], "after": after[name]}
               for name in before if before[name] != after[name]}
    assert set(changed) == {"ItemRepair", "ProblemDescription"}
    assert changed["ItemRepair"]["before"]["instances"][0]["rows"][0][11] == "I01-LRU-DIRP"
    assert changed["ItemRepair"]["after"]["instances"][0]["rows"][0][11] is None
    result = {
        "schema": "simlox-i01-var04-unreferenced-item-repair-exact-diff/v1",
        "referenced_sha256": sha(reference_raw),
        "unreferenced_sha256": sha(unref_raw),
        "changed_tables": changed,
        "unchanged_table_count": len(before) - len(changed),
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(json.dumps({"sha256": sha(raw), "changed": sorted(changed)}))


if __name__ == "__main__":
    main()
