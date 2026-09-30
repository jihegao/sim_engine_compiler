"""Record exact A03 -> A11 source differences, including the paired control."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: t for t in doc["model"]["tables"]}


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for instance in table["instances"] for row in instance["rows"]]


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
            changed[name] = {
                "changed_cells": cells,
                "added_rows": b[len(a):],
                "removed_rows": a[len(b):],
                "columns_changed": left[name]["columns"] != right[name]["columns"],
            }
    return changed


def main() -> int:
    control = HERE / "control-input.json"
    required = HERE / "required-input.json"
    result = {
        "schema": "simlox-a11-exact-source-diff/v1",
        "parent_sha256": sha(PARENT),
        "control_sha256": sha(control),
        "required_sha256": sha(required),
        "parent_to_control": diff(tables(PARENT), tables(control)),
        "control_to_required": diff(tables(control), tables(required)),
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        target.write_bytes(raw)
    print(json.dumps({"parent_to_control_tables": sorted(result["parent_to_control"]), "control_to_required_tables": sorted(result["control_to_required"])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
