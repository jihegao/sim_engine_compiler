"""Describe and verify the frozen E15 donor and arm deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DONOR = HERE.parent / "G01-var03-du-discard-reorder-v1.0.0/native-input.json"
INPUTS = {
    "donor": DONOR,
    "default": HERE / "native-input-default.json",
    "explicit-three": HERE / "native-input-explicit-three.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_map(path: Path) -> dict[str, dict]:
    model = json.loads(path.read_bytes())["model"]
    tables = model["tables"]
    result = {t["name"]: t for t in tables}
    if len(result) != len(tables):
        raise ValueError("duplicate input tables")
    return result


def changes(a: dict[str, dict], b: dict[str, dict]) -> dict:
    if set(a) != set(b):
        raise ValueError("input table set changed")
    result = {}
    for name in sorted(a):
        left, right = a[name], b[name]
        if left == right:
            continue
        if left["columns"] != right["columns"] or len(left["instances"]) != 1 or len(right["instances"]) != 1:
            raise ValueError(f"non-cell delta in {name}")
        old = left["instances"][0]["rows"]
        new = right["instances"][0]["rows"]
        if len(old) != len(new):
            raise ValueError(f"row count changed in {name}")
        columns = [c["name"] for c in left["columns"]]
        edits = []
        for i, (oldrow, newrow) in enumerate(zip(old, new)):
            for field, before, after in zip(columns, oldrow, newrow):
                if before != after:
                    edits.append({"row": i, "field": field, "before": before, "after": after})
        result[name] = edits
    return result


def main() -> None:
    maps = {name: table_map(path) for name, path in INPUTS.items()}
    donor_default = changes(maps["donor"], maps["default"])
    donor_explicit = changes(maps["donor"], maps["explicit-three"])
    pair = changes(maps["default"], maps["explicit-three"])
    if set(donor_default) != {"ProblemDescription", "Item", "StockAllocation"} or set(donor_explicit) != {"ProblemDescription", "Item", "StockAllocation"}:
        raise ValueError("donor delta changed unrelated tables")
    if [x["field"] for x in donor_default["Item"]] != ["TRACK"] or donor_default["Item"] != donor_explicit["Item"]:
        raise ValueError("item tracking delta differs")
    if set(pair) != {"ProblemDescription", "StockAllocation"} or [x["field"] for x in pair["StockAllocation"]] != ["ISTOH"]:
        raise ValueError("pair has extra behavioral differences")
    result = {
        "schema": "simlox-e15-var07-exact-diff/v1",
        "source_sha256": {name: sha(path) for name, path in INPUTS.items()},
        "donor_to_default": donor_default,
        "donor_to_explicit_three": donor_explicit,
        "default_to_explicit_three": pair,
        "unchanged_table_count": len(maps["donor"]) - len(donor_default),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
