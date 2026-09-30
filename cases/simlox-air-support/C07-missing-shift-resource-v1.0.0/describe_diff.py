"""Freeze exact source table deltas before the native C07 row-absence probe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA256


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def diff(a: dict, b: dict) -> list[str]:
    return sorted(name for name in a.keys() | b.keys() if a.get(name) != b.get(name))


def main() -> None:
    parent = tables(PARENT)
    children = {v: tables(HERE / f"{v}-input.json") for v in ("qty-zero", "row-absent")}
    result = {
        "schema": "simlox-c07-missing-shift-resource-exact-diff/v1",
        "parent_sha256": PARENT_SHA256,
        "children": {v: {"sha256": sha(HERE / f"{v}-input.json"),
                         "changed_tables": diff(parent, child)} for v, child in children.items()},
        "pair_changed_tables": diff(children["qty-zero"], children["row-absent"]),
    }
    assert sha(PARENT) == PARENT_SHA256
    assert all(x["changed_tables"] == ["ProblemDescription", "ShiftResource"] for x in result["children"].values())
    assert result["pair_changed_tables"] == ["ProblemDescription", "ShiftResource"]
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
