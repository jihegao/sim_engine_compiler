"""Change accepted I02.var01 IN target to the forbidden <OUTSIDE>."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2" / "native-input.json"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]


def build() -> dict:
    assert sha(PARENT) == PARENT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    assert len(parent["model"]["tables"]) == 32
    row = table(parent, "ItemTransfer")["instances"][0]["rows"]
    assert row == [["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None]]
    child = copy.deepcopy(parent)
    table(child, "ItemTransfer")["instances"][0]["rows"][0][1] = "<OUTSIDE>"
    table(child, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "I02.var14 deliberately invalid ItemTransfer with both endpoints OUTSIDE"
    )
    return child


if __name__ == "__main__":
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "native-input.json"
    if target.exists():
        assert target.read_bytes() == raw, "frozen negative input differs"
    else:
        target.write_bytes(raw)
    print(sha(target), len(raw))
