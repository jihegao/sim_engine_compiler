"""Verify both E01-derived G01.var06 source deltas and their only cross-branch fields."""
from __future__ import annotations

import json
from pathlib import Path

from build import PARENT, PARENT_SHA, OUTPUTS, sha

HERE = Path(__file__).resolve().parent


def tables(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: t for t in d["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted E01 parent changed")
    before = tables(PARENT)
    expected = {
        "identical": ["ItemStructure", "ProblemDescription", "StockAllocation", "System"],
        "similar": ["Item", "ProblemDescription", "StockAllocation", "System"],
    }
    branches = {}
    for kind, path in OUTPUTS.items():
        after = tables(path)
        if set(after) != set(before):
            raise ValueError("table set changed")
        changed = sorted(n for n in before if before[n] != after[n])
        if changed != expected[kind]:
            raise ValueError(f"{kind} changed {changed}")
        branches[kind] = {"input_sha256": sha(path), "changed_tables": changed, "unchanged_tables": len(before) - len(changed), "changes": {n: {"before": before[n]["instances"][0]["rows"], "after": after[n]["instances"][0]["rows"]} for n in changed}}
    result = {"schema": "simlox-g01-var06-parent-diff/v1", "parent_sha256": PARENT_SHA, "branches": branches}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "exact-diff.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("exact diff differs")
    else:
        path.write_bytes(raw)
    print(json.dumps({k: {"sha256": v["input_sha256"], "changed_tables": v["changed_tables"]} for k, v in branches.items()}))


if __name__ == "__main__":
    main()
