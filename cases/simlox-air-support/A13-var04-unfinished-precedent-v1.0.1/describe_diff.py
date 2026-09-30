"""Regenerate the exact table-level delta from accepted A13 source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    parent = tables(json.loads(PARENT.read_text(encoding="utf-8")))
    result = {"schema": "simlox-air-support-exact-table-diff/v1",
              "parent_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(), "variants": {}}
    for variant in ("unfinished-control", "unfinished-dependency"):
        path = HERE / f"{variant}-input.json"
        child = tables(json.loads(path.read_text(encoding="utf-8")))
        assert parent.keys() == child.keys()
        changed = {name: {"before": parent[name]["instances"], "after": tab["instances"]}
                   for name, tab in child.items() if tab != parent[name]}
        result["variants"][variant] = {
            "input_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "changed_tables": changed,
            "unchanged_tables": sorted(name for name in parent if name not in changed)}
    path = HERE / "exact-diff.json"
    path.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
