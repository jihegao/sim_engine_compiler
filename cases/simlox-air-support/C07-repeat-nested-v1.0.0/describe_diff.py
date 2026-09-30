"""Verify exact table-level deltas across the three frozen C07 profile variants."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA256, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    assert sha(PARENT) == PARENT_SHA256
    parent = tables(PARENT)
    children = {v: tables(HERE / f"{v}-input.json") for v in VARIANTS}
    assert all(parent.keys() == x.keys() for x in children.values())
    result = {"schema": "simlox-c07-repeat-nested-exact-diff/v1", "parent_sha256": PARENT_SHA256,
              "variants": {v: {"sha256": sha(HERE / f"{v}-input.json"),
                               "changed_tables": sorted(k for k in parent if parent[k] != child[k])}
                           for v, child in children.items()},
              "pair_changed_tables": {f"{a}-vs-{b}": sorted(k for k in parent if children[a][k] != children[b][k])
                                      for a, b in (("explicit", "repeated"), ("explicit", "nested"), ("repeated", "nested"))}}
    assert all(x["changed_tables"] == ["ProblemDescription", "ShiftProfile"] for x in result["variants"].values())
    assert all(x == ["ProblemDescription", "ShiftProfile"] for x in result["pair_changed_tables"].values())
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
