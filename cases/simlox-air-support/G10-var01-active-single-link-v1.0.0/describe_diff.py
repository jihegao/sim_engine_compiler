"""Verify the exact accepted G01.var05 to G10.var01 table delta."""
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
    if set(after) - set(before) != {"Redundancy"} or set(before) - set(after):
        raise ValueError("unexpected table set delta")
    changed = sorted(n for n in set(before) & set(after) if before[n] != after[n])
    if changed != ["Control", "ProblemDescription"]:
        raise ValueError(f"unexpected changed tables: {changed}")
    result = {
        "schema": "simlox-g10-var01-parent-diff/v1",
        "parent_sha256": PARENT_SHA,
        "child_sha256": sha(OUTPUT.read_bytes()),
        "changed_tables": changed,
        "added_tables": ["Redundancy"],
        "unchanged_tables": len(before) - len(changed),
        "changes": {n: {"before": before[n]["instances"][0]["rows"], "after": after[n]["instances"][0]["rows"]} for n in changed},
        "redundancy": after["Redundancy"],
    }
    path = OUTPUT.parent / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("exact diff differs")
    else:
        path.write_bytes(raw)
    print(json.dumps({"changed_tables": changed, "added_tables": ["Redundancy"], "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
