"""Produce a deterministic exact source-table delta for the frozen A15 pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J07-unit-type-report-v1.0.0" / "native-input.json"
OUTPUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def main() -> None:
    parent = tables(PARENT)
    paths = {
        "a-hour-b-mission": HERE / "a-hour-b-mission-input.json",
        "a-mission-b-hour": HERE / "a-mission-b-hour-input.json",
    }
    children = {key: tables(path) for key, path in paths.items()}
    changed = {}
    for variant, child in children.items():
        old = sorted(name for name in parent if name in child and child[name] != parent[name])
        added = sorted(set(child) - set(parent))
        removed = sorted(set(parent) - set(child))
        assert old == ["OperationParameter", "ProblemDescription"]
        assert added == ["MissionTypeUtilization"] and not removed
        changed[variant] = {
            "modified": {name: {"parent": parent[name], "child": child[name]} for name in old},
            "added": {name: child[name] for name in added},
            "unchanged_parent_tables": len(parent) - len(old),
        }
    pair = sorted(name for name in children["a-hour-b-mission"] if children["a-hour-b-mission"][name] != children["a-mission-b-hour"][name])
    assert pair == ["MissionTypeUtilization", "ProblemDescription"]
    out = {
        "schema": "simlox-a15-two-unit-custom-exposure-exact-diff/v1",
        "parent_sha256": sha(PARENT),
        "child_sha256": {key: sha(path) for key, path in paths.items()},
        "pair_different_tables": pair,
        "changes": changed,
    }
    data = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == data, "frozen diff changed"
    else:
        OUTPUT.write_bytes(data)
    print(sha(OUTPUT))


if __name__ == "__main__":
    main()
