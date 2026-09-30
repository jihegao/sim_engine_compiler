"""Rebuild exact table deltas from accepted A13, with A17 topology fingerprint."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A13-start-dependence-v1.0.0" / "dependent-input.json"
STRUCTURE = ROOT / "A17-multi-unit-group-v1.0.0" / "native-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
STRUCTURE_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"


def tables(path: Path) -> dict[str, dict]:
    source = json.loads(path.read_text(encoding="utf-8"))
    result = {t["name"]: t for t in source["model"]["tables"]}
    if len(result) != len(source["model"]["tables"]):
        raise ValueError(f"duplicate table: {path}")
    return result


def main() -> None:
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA or hashlib.sha256(STRUCTURE.read_bytes()).hexdigest() != STRUCTURE_SHA:
        raise ValueError("accepted source fingerprint changed")
    parent = tables(PARENT)
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "parent_sha256": PARENT_SHA, "structural_source_sha256": STRUCTURE_SHA, "variants": {}}
    for name in ("control", "dependency"):
        path = HERE / f"{name}-input.json"
        child = tables(path)
        changes = {
            table: {"before": parent[table]["instances"] if table in parent else None,
                    "after": child[table]["instances"] if table in child else None}
            for table in sorted(parent.keys() | child.keys()) if parent.get(table) != child.get(table)
        }
        result["variants"][name] = {
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "changed_tables": changes,
            "unchanged_tables": sorted((parent.keys() & child.keys()) - changes.keys()),
        }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("frozen diff changed")
    target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
