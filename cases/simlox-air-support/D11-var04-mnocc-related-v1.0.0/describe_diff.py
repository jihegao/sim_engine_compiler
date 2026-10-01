"""Freeze parent and pairwise table deltas for related MNOCC candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D10-var01-missions-v1.0.0" / "native-input.json"
PARENT_SHA = "6607991260e3f911d0121c7949443409a57937e95f80c7e4f3a2faa6ac20ba72"
PARENT_CHANGED = ["MaterielPM", "PMLocation", "ProblemDescription", "TaskBreakDown", "Tasks"]
PAIR_CHANGED = ["MaterielPM", "ProblemDescription"]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    return {table["name"]: table for table in json.loads(raw)["model"]["tables"]}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError("frozen D10.var01 parent differs")
    before = tables(parent_raw)
    branches = {}
    snapshots = {}
    for cap in (2, 3):
        raw = (HERE / f"native-related-cap-{cap}.json").read_bytes()
        after = tables(raw)
        if set(after) != set(before):
            raise ValueError("unexpected table addition or removal")
        changed = sorted(name for name in before if before[name] != after[name])
        if changed != PARENT_CHANGED:
            raise ValueError(f"unexpected parent changes for cap {cap}: {changed}")
        branches[str(cap)] = {"child_sha256": sha(raw), "changed_tables": changed,
                              "unchanged_tables": len(before) - len(changed),
                              "changes": {name: {"before": before[name]["instances"][0]["rows"],
                                                 "after": after[name]["instances"][0]["rows"]}
                                          for name in changed}}
        snapshots[cap] = after
    pair_changed = sorted(name for name in before if snapshots[2][name] != snapshots[3][name])
    if pair_changed != PAIR_CHANGED:
        raise ValueError(f"unexpected pairwise changes: {pair_changed}")
    result = {"schema": "simlox-d11-mnocc-related-parent-diff/v1", "parent_sha256": PARENT_SHA,
              "branches": branches, "pairwise_changed_tables": pair_changed}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "exact-diff.json"
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    if not path.exists():
        path.write_bytes(raw)
    print(json.dumps({"diff_sha256": sha(raw), "pairwise_changed_tables": pair_changed}))


if __name__ == "__main__":
    main()
