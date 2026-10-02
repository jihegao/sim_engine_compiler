"""Freeze a stock-only two-POINT APID contrast from accepted E01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def row(doc: dict, name: str) -> list:
    rows = table(doc, name)["instances"][0]["rows"]
    assert len(rows) == 1
    return rows[0]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = json.loads(PARENT.read_bytes())
    assert row(parent, "Control")[3] == "AIR_BASIC"
    assert row(parent, "StockAllocation")[:4] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1]
    assert table(parent, "ResourceAllocation")["instances"][0]["rows"] == []
    assert not any(t["name"] == "MaintenanceAllocation" for t in parent["model"]["tables"])
    control = copy.deepcopy(parent)
    stock_rows = table(control, "StockAllocation")["instances"][0]["rows"]
    stock_rows.append(["AIR_EMPTY", "TEACH-LRU-01", "BASE-01", 0, None, None, None, None, None])
    row(control, "ProblemDescription")[0] = "I01.var01 two stock POINTs, APID AIR_BASIC selects local spare"
    empty = copy.deepcopy(control)
    row(empty, "Control")[3] = "AIR_EMPTY"
    row(empty, "ProblemDescription")[0] = "I01.var01 two stock POINTs, APID AIR_EMPTY selects zero spare"
    for name, doc in (("stocked-input.json", control), ("empty-input.json", empty)):
        path = HERE / name
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen source differs: {name}")
        if not path.exists():
            path.write_bytes(raw)
        print(name, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
