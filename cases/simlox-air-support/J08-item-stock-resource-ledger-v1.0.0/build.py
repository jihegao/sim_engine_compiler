"""Freeze tracked item reporting on the accepted F02 risk fleet."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2" / "risk-input.json"
PARENT_SHA = "ae46b08a6ef6fd063906b888fb3c73fba06edcb57acc1a4ade49fc62c53fd7d3"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    result = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(result) == 1, name
    return result[0]


def build() -> dict:
    source = PARENT.read_bytes()
    assert sha(source) == PARENT_SHA
    parent = json.loads(source)
    child = copy.deepcopy(parent)
    item = table(child, "Item")
    names = [c["name"] for c in item["columns"]]
    rows = item["instances"][0]["rows"]
    assert len(rows) == 2 and [r[names.index("IID")] for r in rows] == ["TEACH-LRU-01", "TEACH-SRU-01"]
    assert all(r[names.index("TRACK")] is None for r in rows)
    for row in rows:
        row[names.index("TRACK")] = "Y"
    collection = table(child, "ResultCollection")["instances"][0]["rows"]
    assert collection == [["MISSION", 0.5, 0, 60.0, None, None], ["SYSTEM", 0.5, 0, 60.0, None, None]]
    collection.append(["ITEM", 0.5, 0, 60.0, None, None])
    return child


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "native-input.json"
    if target.exists():
        assert target.read_bytes() == raw, "frozen input changed"
    else:
        target.write_bytes(raw)
    print(json.dumps({"input_sha256": sha(raw), "parent_sha256": PARENT_SHA}))


if __name__ == "__main__":
    main()
