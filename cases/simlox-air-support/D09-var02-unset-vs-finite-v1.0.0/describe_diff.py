"""Assert the unset control changes only NCFTL and description."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT, PARENT_SHA, build


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    return {table["name"]: table for table in doc["model"]["tables"]}


def row(table: dict) -> dict:
    names = [column["name"] for column in table["columns"]]
    rows = [dict(zip(names, value, strict=True)) for instance in table["instances"] for value in instance["rows"]]
    assert len(rows) == 1
    return rows[0]


def main() -> None:
    child_path = HERE / "native-input-unset.json"
    assert sha(PARENT) == PARENT_SHA and child_path.read_bytes() == build()
    parent, child = tables(PARENT), tables(child_path)
    assert parent.keys() == child.keys()
    different = sorted(name for name in parent if parent[name] != child[name])
    assert different == ["Item", "ProblemDescription"]
    changes = {}
    for name in different:
        assert parent[name]["columns"] == child[name]["columns"]
        before, after = row(parent[name]), row(child[name])
        changes[name] = {key: {"before": before[key], "after": after[key]} for key in before if before[key] != after[key]}
    assert changes["Item"] == {"NCFTL": {"before": 0.2, "after": None}}
    assert set(changes["ProblemDescription"]) == {"PDESC"}
    result = {"schema": "simlox-d09-var02-exact-diff/v1", "parent_input_sha256": PARENT_SHA, "child_input_sha256": sha(child_path), "changed_tables": changes, "identical_tables": len(parent) - 2}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "exact-diff.json"
    assert len(sys.argv) in (1, 2)
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        output.write_bytes(raw)
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"input_sha256": sha(child_path), "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
