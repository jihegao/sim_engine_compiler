"""Verify the exact accepted DP to seed-1 SPRU source-table delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import PARENT, PARENT_SHA, OUTPUT

EXPECTED = ["Item", "ItemReorder", "ItemRepair", "ItemReplacement", "ItemStructure", "ProblemDescription", "StockAllocation"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted parent differs")
    before, after = tables(PARENT), tables(OUTPUT)
    if set(before) != set(after):
        raise ValueError("source table set differs")
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != EXPECTED:
        raise ValueError(f"unexpected changed tables: {changed}")
    result = {
        "schema": "simlox-g01-var02-spru-parent-diff/v1",
        "parent_sha256": PARENT_SHA,
        "child_sha256": sha(OUTPUT),
        "changed_tables": changed,
        "unchanged_tables": len(before) - len(changed),
        "changes": {name: {"before": before[name]["instances"][0]["rows"], "after": after[name]["instances"][0]["rows"]} for name in changed},
    }
    output = OUTPUT.parent / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError("exact diff differs")
    else:
        output.write_bytes(raw)
    print(json.dumps({"changed_tables": changed, "unchanged_tables": result["unchanged_tables"], "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
