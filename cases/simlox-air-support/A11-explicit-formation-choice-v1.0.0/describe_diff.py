"""Record exact accepted-parent and paired A11 formation-source differences."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json"
VARIANTS = ("ab-high", "aa-high", "b-missing")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: t for t in doc["model"]["tables"]}


def records(tab: dict) -> list[dict]:
    names = [c["name"] for c in tab["columns"]]
    return [dict(zip(names, row)) for i in tab["instances"] for row in i["rows"]]


def diff(left: dict, right: dict) -> dict:
    changed = {}
    for name in sorted(set(left) | set(right)):
        if name not in left:
            changed[name] = {"added_rows": records(right[name])}
        elif name not in right:
            changed[name] = {"removed_rows": records(left[name])}
        elif left[name] != right[name]:
            a, b = records(left[name]), records(right[name])
            cells = []
            for i in range(min(len(a), len(b))):
                for field in sorted(set(a[i]) | set(b[i])):
                    if a[i].get(field) != b[i].get(field):
                        cells.append({"row": i, "field": field, "before": a[i].get(field), "after": b[i].get(field)})
            changed[name] = {"changed_cells": cells, "added_rows": b[len(a):], "removed_rows": a[len(b):], "columns_changed": left[name]["columns"] != right[name]["columns"]}
    return changed


def main() -> int:
    paths = {v: HERE / f"{v}-input.json" for v in VARIANTS}
    result = {
        "schema": "simlox-a11-explicit-formation-exact-source-diff/v1",
        "parent_sha256": sha(PARENT),
        "variant_sha256": {v: sha(path) for v, path in paths.items()},
        "parent_to_variant": {v: diff(tables(PARENT), tables(path)) for v, path in paths.items()},
        "ab_high_to_aa_high": diff(tables(paths["ab-high"]), tables(paths["aa-high"])),
        "ab_high_to_b_missing": diff(tables(paths["ab-high"]), tables(paths["b-missing"])),
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        target.write_bytes(raw)
    print(json.dumps({"parent_to_variant_tables": {v: sorted(changed) for v, changed in result["parent_to_variant"].items()}, "priority_swap_tables": sorted(result["ab_high_to_aa_high"]), "fallback_change_tables": sorted(result["ab_high_to_b_missing"])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
