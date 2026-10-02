"""Verify only the declared D08.var01 mission reliability cells change."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0/native-input.json"
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {table["name"]: table for table in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def fields(table: dict) -> list[dict]:
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    parent = keyed(PARENT)
    arms = {arm: keyed(HERE / f"native-input-{arm}.json") for arm in ("default", "low")}
    assert all(set(child) == set(parent) for child in arms.values())
    assert len(parent) == 31
    changes = {}
    for arm, child in arms.items():
        change = []
        for name in parent:
            before, after = fields(parent[name]), fields(child[name])
            assert len(before) == len(after)
            for row_index, (old, new) in enumerate(zip(before, after)):
                for field in old:
                    if old[field] != new[field]:
                        change.append({"table": name, "row": row_index, "field": field, "before": old[field], "after": new[field]})
        assert len(change) == 2
        assert {(c["table"], c["field"]) for c in change} == {("ProblemDescription", "PDESC"), ("MissionType", "MFF")}
        assert next(c for c in change if c["table"] == "MissionType")["before"] == 1.0
        assert next(c for c in change if c["table"] == "MissionType")["after"] == (None if arm == "default" else 0.000001)
        changes[arm] = change
    result = {"schema": "simlox-d08-var01-mff-exact-diff/v1", "parent_sha256": sha(PARENT), "source_sha256": {arm: sha(HERE / f"native-input-{arm}.json") for arm in arms}, "changes_from_parent": changes, "unchanged_tables": 29, "pairwise_business_difference": {"table": "MissionType", "row": 1, "field": "MFF", "default": None, "low": 0.000001}}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        OUT.write_bytes(raw)
    else:
        assert len(sys.argv) == 1 and OUT.read_bytes() == raw
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
