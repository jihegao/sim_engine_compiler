"""Verify the G01.var06 similar-parent to indexed-stockout source delta."""
from __future__ import annotations

import json
from pathlib import Path

from build import PARENT, PARENT_SHA, OUTPUT, sha


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("parent hash differs")
    before, after = tables(PARENT), tables(OUTPUT)
    if set(before) != set(after):
        raise ValueError("table set differs")
    changed = sorted(n for n in before if before[n] != after[n])
    if changed != ["ItemRepair", "ProblemDescription", "StockAllocation"]:
        raise ValueError(f"unexpected changed tables: {changed}")
    result = {
        "schema": "simlox-g01-var06-index-stockout-parent-diff/v1",
        "parent_sha256": PARENT_SHA,
        "child_sha256": sha(OUTPUT),
        "changed_tables": changed,
        "unchanged_tables": len(before) - len(changed),
        "changes": {n: {"before": before[n]["instances"][0]["rows"], "after": after[n]["instances"][0]["rows"]} for n in changed},
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = OUTPUT.parent / "exact-diff.json"
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("exact diff differs")
    else:
        path.write_bytes(raw)
    print(json.dumps({"changed_tables": changed, "unchanged_tables": len(before) - len(changed), "child_sha256": sha(OUTPUT)}))


if __name__ == "__main__":
    main()
