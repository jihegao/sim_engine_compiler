"""Rebuild the exact table-level delta from accepted A13 source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"


def by_name(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    parent = by_name(json.loads(PARENT.read_text(encoding="utf-8")))
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "parent_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(), "variants": {}}
    for name in ("failure-control", "failure-dependency"):
        p = HERE / f"{name}-input.json"
        child = by_name(json.loads(p.read_text(encoding="utf-8")))
        assert parent.keys() == child.keys()
        changes = {t: {"before": parent[t]["instances"], "after": child[t]["instances"]}
                   for t in parent if parent[t] != child[t]}
        result["variants"][name] = {"input_sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                                     "changed_tables": changes,
                                     "unchanged_tables": sorted(t for t in parent if t not in changes)}
    out = HERE / "exact-diff.json"
    out.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
