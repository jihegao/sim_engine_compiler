"""Freeze selected versus blank APID from accepted I01.var01 stock case."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var01-two-stock-points-v1.0.0/stocked-input.json"
PARENT_SHA = "9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def row(doc: dict, name: str) -> list:
    table = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(table) == 1 and len(table[0]["instances"]) == 1
    rows = table[0]["instances"][0]["rows"]
    assert len(rows) == 1
    return rows[0]


def main() -> None:
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    selected = json.loads(parent_raw)
    assert row(selected, "Control")[3] == "AIR_BASIC"
    blank = copy.deepcopy(selected)
    row(blank, "Control")[3] = None
    row(blank, "ProblemDescription")[0] = "I01.var02 two stock POINTs, Control.APID blank"
    for name, raw in (("selected-input.json", parent_raw),
                      ("blank-input.json", (json.dumps(blank, ensure_ascii=False, indent=2) + "\n").encode())):
        path = HERE / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen source differs: {name}")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(raw))


if __name__ == "__main__":
    main()
