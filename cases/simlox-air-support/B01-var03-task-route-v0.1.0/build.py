"""Freeze a one-cell explicit task-route contrast from accepted B03 1.0.2."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B03-explicit-cold-hot-v1.0.2" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA256 = "9c6b3c8955089b89caa1a71634eb78e9fd52069d5d710273e3a6bc710e19222c"
OLD = b'"COLD-FIRST",\n                8.0,'
NEW = b'"HOT-SORTIE",\n                8.0,'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(model: dict, name: str) -> dict:
    return next(t for t in model["model"]["tables"] if t["name"] == name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    parent = PARENT.read_bytes()
    assert sha256(parent) == PARENT_SHA256
    assert parent.count(OLD) == 1
    child = parent.replace(OLD, NEW)
    p = json.loads(parent)
    c = json.loads(child)
    pt = table(p, "OperationProfile")
    ct = table(c, "OperationProfile")
    assert len(pt["instances"]) == len(ct["instances"]) == 1
    rows = pt["instances"][0]["rows"]
    changed = ct["instances"][0]["rows"]
    assert len(rows) == len(changed) == 3
    assert rows[0][0:3] == ["BASIC-SCHEDULE", "COLD-FIRST", 8.0]
    assert changed[0][0:3] == ["BASIC-SCHEDULE", "HOT-SORTIE", 8.0]
    assert changed[0][0] == rows[0][0] and changed[0][2:] == rows[0][2:]
    assert changed[1:] == rows[1:]
    ct["instances"][0]["rows"] = rows
    assert c == p
    if args.check:
        assert CHILD.read_bytes() == child
    else:
        CHILD.write_bytes(child)
    print(json.dumps({"parent_sha256": sha256(parent), "child_sha256": sha256(child), "only_cell": "OperationProfile[0].SPRID COLD-FIRST -> HOT-SORTIE", "checked": args.check}))


if __name__ == "__main__":
    main()
