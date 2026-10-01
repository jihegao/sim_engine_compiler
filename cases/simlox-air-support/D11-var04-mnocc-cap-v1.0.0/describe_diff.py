"""Freeze exact parent and pairwise deltas for the MNOCC cap branches."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D10-var02-multi-counter-v1.0.0" / "native-input.json"
PARENT_SHA = "0083ffd0038017be0078d9afd5a9e892b3df8c7ae5eafd89b8280950816aa829"
EXPECTED = ["MaterielPM", "ProblemDescription"]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    return {table["name"]: table for table in json.loads(raw)["model"]["tables"]}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError("frozen D10.var02 parent differs")
    before = tables(parent_raw)
    branches = {}
    child_tables = {}
    for limit in (0, 1, 2):
        child_raw = (HERE / f"native-mnocc-{limit}.json").read_bytes()
        after = tables(child_raw)
        if set(before) != set(after):
            raise ValueError(f"table set differs for MNOCC={limit}")
        changed = sorted(name for name in before if before[name] != after[name])
        if changed != EXPECTED:
            raise ValueError(f"unexpected parent delta for MNOCC={limit}: {changed}")
        pm = after["MaterielPM"]
        column_names = [column["name"] for column in pm["columns"]]
        if pm["instances"][0]["rows"][0][column_names.index("MNOCC")] != limit:
            raise ValueError(f"wrong MNOCC value for branch {limit}")
        branches[str(limit)] = {
            "child_sha256": sha(child_raw),
            "changed_tables": changed,
            "unchanged_tables": len(before) - len(changed),
            "changes": {name: {"before": before[name]["instances"][0]["rows"],
                               "after": after[name]["instances"][0]["rows"]}
                        for name in changed},
        }
        child_tables[limit] = after
    for lower, upper in ((0, 1), (1, 2)):
        changed = sorted(name for name in before if child_tables[lower][name] != child_tables[upper][name])
        if changed != EXPECTED:
            raise ValueError(f"unexpected pairwise delta {lower}->{upper}: {changed}")
    result = {"schema": "simlox-d11-mnocc-cap-parent-diff/v1", "parent_sha256": PARENT_SHA,
              "branches": branches, "pairwise_changed_tables": EXPECTED}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "exact-diff.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"branch_sha256": {key: value["child_sha256"] for key, value in branches.items()},
                      "diff_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
