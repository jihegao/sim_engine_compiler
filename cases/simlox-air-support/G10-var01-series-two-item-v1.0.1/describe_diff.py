"""Verify exact two-item RedundancyLink expansion from accepted G10.var03."""
from __future__ import annotations

import hashlib
import json

from build import PARENT, PARENT_SHA, OUTPUT, sha


def tables(path):
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    if sha(PARENT.read_bytes()) != PARENT_SHA:
        raise ValueError("parent hash differs")
    before, after = tables(PARENT), tables(OUTPUT)
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(name for name in before.keys() & after.keys() if before[name] != after[name])
    if added != ["RedundancyLink"] or removed or changed != ["Item", "ItemRepair", "ItemStructure", "ProblemDescription", "Redundancy", "StockAllocation", "System"]:
        raise ValueError(f"unexpected table delta: added={added}, removed={removed}, changed={changed}")
    result = {
        "schema": "simlox-g10-var01-v101-parent-diff/v1",
        "parent_sha256": PARENT_SHA,
        "child_sha256": sha(OUTPUT.read_bytes()),
        "added_tables": added,
        "removed_tables": removed,
        "changed_tables": changed,
        "unchanged_tables": len(before) - len(changed),
        "changes": {name: {"before": before[name]["instances"][0]["rows"], "after": after[name]["instances"][0]["rows"]} for name in changed},
        "additions": {name: after[name] for name in added},
    }
    path = OUTPUT.parent / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("exact diff differs")
    else:
        path.write_bytes(raw)
    print(json.dumps({"added_tables": added, "changed_tables": changed, "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
