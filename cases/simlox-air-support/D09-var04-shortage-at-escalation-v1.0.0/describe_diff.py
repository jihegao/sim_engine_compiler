"""Assert complete parent deltas and matched shortage-arm differences."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import ARMS, HERE, PARENT, build

OUTPUT = HERE / "exact-diff.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    doc = json.loads(raw)
    result = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def delta(left: dict, right: dict) -> dict:
    assert left.keys() == right.keys() and len(left) == 31
    changes = {}
    for name in left:
        before, after = left[name], right[name]
        assert before["columns"] == after["columns"] and len(before["instances"]) == len(after["instances"]) == 1
        x, y = before["instances"][0]["rows"], after["instances"][0]["rows"]
        if x == y:
            continue
        cols = [c["name"] for c in before["columns"]]
        if len(x) == len(y) == 1:
            changes[name] = {col: {"before": a, "after": b} for col, a, b in zip(cols, x[0], y[0], strict=True) if a != b}
        else:
            assert not x and y
            changes[name] = {"added_rows": [dict(zip(cols, row, strict=True)) for row in y]}
    return changes


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    parent_raw = PARENT.read_bytes()
    parent = tables(parent_raw)
    children = {}
    for arm, (stock, crew) in ARMS.items():
        raw = build(arm)
        path = HERE / f"native-input-{arm}.json"
        assert path.read_bytes() == raw
        changes = delta(parent, tables(raw))
        assert set(changes) == {"ProblemDescription", "SystemRepair", "StockAllocation", "Tasks", "TaskBreakDown", "Resource", "ResourceAllocation", "SubTaskResource"} - ({"StockAllocation"} if stock == 0 else set())
        assert changes["SystemRepair"] == {"SURPTID": {"before": None, "after": "D09-SURP"}}
        assert changes["ResourceAllocation"]["added_rows"][0]["RQTY"] == crew
        if stock:
            assert changes["StockAllocation"] == {"STSIZ": {"before": 0, "after": 1}}
        children[arm] = {"input_sha256": sha(raw), "changed_tables": changes, "identical_tables": 31 - len(changes)}
    a, b, c = (tables(build(arm)) for arm in ARMS)
    ab, ac, bc = delta(a, b), delta(a, c), delta(b, c)
    assert set(ab) == {"ProblemDescription", "StockAllocation", "ResourceAllocation"}
    assert set(ac) == {"ProblemDescription", "StockAllocation"}
    assert ab["StockAllocation"] == ac["StockAllocation"] == {"STSIZ": {"before": 0, "after": 1}}
    assert ab["ResourceAllocation"] == {"RQTY": {"before": 1, "after": 0}}
    assert set(bc) == {"ProblemDescription", "ResourceAllocation"}
    assert bc["ResourceAllocation"] == {"RQTY": {"before": 0, "after": 1}}
    result = {"schema": "simlox-d09-var04-shortage-exact-diff/v1", "parent_input_sha256": sha(parent_raw), "children": children, "arm_contrasts": {"part_to_crew": ab, "part_to_supplied": ac, "crew_to_supplied": bc}}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if write:
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(json.dumps({**{arm: children[arm]["input_sha256"] for arm in ARMS}, "diff_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
