"""Freeze the exact zero-delay to two-hour transfer delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {item["name"]: item for item in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def main() -> None:
    child = HERE / "native-input.json"
    assert sha(PARENT) == PARENT_SHA
    left, right = tables(PARENT), tables(child)
    added = {name: right[name] for name in sorted(right.keys() - left.keys())}
    removed = {name: left[name] for name in sorted(left.keys() - right.keys())}
    changed = {name: {"before": left[name], "after": right[name]}
               for name in sorted(left.keys() & right.keys()) if left[name] != right[name]}
    assert not added and not removed
    assert set(changed) == {"ProblemDescription", "ItemTransfer"}
    assert changed["ItemTransfer"]["before"]["instances"][0]["rows"][1] == [
        "DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None]
    assert changed["ItemTransfer"]["after"]["instances"][0]["rows"][1] == [
        "DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 2.0, None]
    result = {"schema": "simlox-i02-var04-between-delay-exact-diff/v1",
              "parent_sha256": sha(PARENT), "child_sha256": sha(child),
              "added_tables": added, "removed_tables": removed,
              "changed_tables": changed,
              "unchanged_table_count": len(left) - len(changed)}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"sha256": sha(output), "unchanged_table_count": result["unchanged_table_count"]}))


if __name__ == "__main__":
    main()
