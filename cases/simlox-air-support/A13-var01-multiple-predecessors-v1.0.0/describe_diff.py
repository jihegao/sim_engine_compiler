"""Materialize exact parent-to-variant business-table changes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
SOURCES = ("control", "single", "multiple")


def tables(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = {t["name"]: t for t in doc["model"]["tables"]}
    if len(result) != len(doc["model"]["tables"]):
        raise ValueError(f"duplicate table in {path}")
    return result


def main() -> None:
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A13 source changed")
    before = tables(PARENT)
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "parent_sha256": PARENT_SHA, "variants": {}}
    for name in SOURCES:
        path = HERE / f"{name}-input.json"
        after = tables(path)
        changes = {
            table: {"before": before[table]["instances"] if table in before else None,
                    "after": after[table]["instances"] if table in after else None}
            for table in sorted(before.keys() | after.keys()) if before.get(table) != after.get(table)
        }
        result["variants"][name] = {
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "changed_tables": changes,
            "unchanged_tables": sorted((before.keys() & after.keys()) - changes.keys()),
        }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "exact-diff.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen exact diff changed")
    output.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
