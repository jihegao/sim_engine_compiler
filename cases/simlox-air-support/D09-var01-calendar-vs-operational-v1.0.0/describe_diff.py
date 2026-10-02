"""Assert the D09.var01 children have only the frozen parent deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import ARMS, HERE, PARENT, PARENT_SHA, build


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    return {table["name"]: table for table in doc["model"]["tables"]}


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = as_tables(PARENT)
    result = {"schema": "simlox-d09-var01-exact-diff/v1", "parent_input_sha256": PARENT_SHA, "children": {}}
    for arm in ARMS:
        path = HERE / f"native-input-{arm}.json"
        assert path.read_bytes() == build(arm)
        child = as_tables(path)
        assert parent.keys() == child.keys()
        different = sorted(name for name in parent if parent[name] != child[name])
        assert different == ["Item", "ProblemDescription", "StockAllocation"]
        changes = {}
        for name in different:
            assert parent[name]["columns"] == child[name]["columns"]
            before, after = rows(parent[name]), rows(child[name])
            assert len(before) == len(after) == 1
            changes[name] = {key: {"before": before[0][key], "after": after[0][key]} for key in before[0] if before[0][key] != after[0][key]}
        assert set(changes["Item"]) == {"NCFTL", "NCFTT"}
        assert set(changes["StockAllocation"]) == {"STSIZ"}
        assert set(changes["ProblemDescription"]) == {"PDESC"}
        result["children"][arm] = {"input_sha256": sha(path), "changed_tables": changes, "identical_tables": len(parent) - len(different)}
    assert len(sys.argv) in (1, 2)
    output = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        output.write_bytes(raw)
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"calendar": result["children"]["calendar"]["input_sha256"], "operational": result["children"]["operational"]["input_sha256"], "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
