"""Assert frozen three-LRU/MAXNC parent deltas and matched arms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import ARMS, HERE, PARENT, PARENT_SHA, build


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    return {table["name"]: table for table in doc["model"]["tables"]}


def row(table: dict) -> dict:
    names = [column["name"] for column in table["columns"]]
    values = [dict(zip(names, raw, strict=True)) for instance in table["instances"] for raw in instance["rows"]]
    assert len(values) == 1
    return values[0]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = tables(PARENT)
    result = {"schema": "simlox-d09-var03-maxnc-exact-diff/v1", "parent_input_sha256": PARENT_SHA, "children": {}}
    for arm, threshold in ARMS.items():
        path = HERE / f"native-input-{arm}.json"
        assert path.read_bytes() == build(arm)
        child = tables(path)
        assert parent.keys() == child.keys()
        changed_names = sorted(name for name in parent if parent[name] != child[name])
        assert changed_names == ["Item", "ItemStructure", "ProblemDescription", "System"]
        changes = {}
        for name in changed_names:
            assert parent[name]["columns"] == child[name]["columns"]
            before, after = row(parent[name]), row(child[name])
            changes[name] = {key: {"before": before[key], "after": after[key]} for key in before if before[key] != after[key]}
        assert changes["Item"] == {"FRT": {"before": 300000, "after": 3000000}}
        assert changes["ItemStructure"] == {"QTYPM": {"before": 1, "after": 3}}
        assert changes["System"] == {"FRT": {"before": 300000, "after": 9000000}, "MAXNC": {"before": None, "after": threshold}}
        assert set(changes["ProblemDescription"]) == {"PDESC"}
        result["children"][arm] = {"input_sha256": sha(path), "changed_tables": changes, "identical_tables": len(parent) - len(changed_names)}
    left, right = tables(HERE / "native-input-limit-2.json"), tables(HERE / "native-input-limit-3.json")
    assert sorted(name for name in left if left[name] != right[name]) == ["ProblemDescription", "System"]
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    assert len(sys.argv) in (1, 2)
    output = HERE / "exact-diff.json"
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        output.write_bytes(raw)
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"limit-2": result["children"]["limit-2"]["input_sha256"], "limit-3": result["children"]["limit-3"]["input_sha256"], "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
