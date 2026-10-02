"""Verify exact parent-to-child criticality cell changes for both routes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import PARENTS

HERE = Path(__file__).resolve().parent
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    result = {table["name"]: table for table in tables}
    assert len(result) == len(tables)
    return result


def rows(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    records = {}
    for arm, (parent_path, parent_sha, target_table, target_field) in PARENTS.items():
        source_path = HERE / f"native-input-{arm}.json"
        parent, child = keyed(parent_path), keyed(source_path)
        assert sha(parent_path) == parent_sha and set(parent) == set(child)
        changes = []
        for table_name in parent:
            before, after = rows(parent[table_name]), rows(child[table_name])
            assert len(before) == len(after)
            for row_index, (old, new) in enumerate(zip(before, after)):
                assert old.keys() == new.keys()
                for field in old:
                    if old[field] != new[field]:
                        changes.append({"table": table_name, "row": row_index, "field": field, "before": old[field], "after": new[field]})
        assert len(changes) == 2 and {(x["table"], x["field"]) for x in changes} == {("ProblemDescription", "PDESC"), (target_table, target_field)}
        key = next(x for x in changes if x["table"] == target_table)
        assert key["before"] == 1.0 and key["after"] == 0.0
        records[arm] = {"parent_sha256": parent_sha, "child_sha256": sha(source_path), "changes": changes, "unchanged_tables": len(parent) - 2, "parent_table_count": len(parent)}
    result = {"schema": "simlox-d08-var03-criticality-exact-diff/v1", "arms": records}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        OUT.write_bytes(raw)
    else:
        assert len(sys.argv) == 1 and OUT.read_bytes() == raw
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
