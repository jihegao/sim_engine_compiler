"""Freeze exact parent/child and paired table differences before native runs."""
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
    children = {value: tables(HERE / f"draos-{value.lower()}-input.json") for value in ("Y", "N")}
    result = {
        "schema": "simlox-c07-cross-shift-exact-diff/v1",
        "parent_sha256": PARENT_SHA256,
        "children": {value: {"sha256": sha(HERE / f"draos-{value.lower()}-input.json"),
                              "changed_tables": diff(parent, child)} for value, child in children.items()},
        "pair_changed_tables": diff(children["Y"], children["N"]),
    }
    assert sha(PARENT) == PARENT_SHA256
    assert result["children"]["Y"]["changed_tables"] == ["MissionPreparation", "MissionType", "OperationProfile", "ProblemDescription", "ShiftProfile", "ShiftResource", "TaskBreakDown", "Tasks"]
    assert result["children"]["N"]["changed_tables"] == ["Control"] + result["children"]["Y"]["changed_tables"]
    assert result["pair_changed_tables"] == ["Control", "ProblemDescription"]
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
