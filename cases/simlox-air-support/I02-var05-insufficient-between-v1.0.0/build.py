"""Freeze a quantity-three BETWEEN request against the accepted one-unit case."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var03-between-transfer-v1.0.0/native-input.json"
PARENT_SHA = "4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1
    return found[0]


def build() -> dict:
    source = PARENT.read_bytes()
    assert sha(source) == PARENT_SHA
    parent = json.loads(source)
    transfer = table(parent, "ItemTransfer")
    assert transfer["instances"][0]["rows"] == [
        ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None],
        ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None]]
    child = copy.deepcopy(parent)
    table(child, "ProblemDescription")["instances"][0]["rows"] = [
        ["I02.var05 request three LRU DEPOT-01 to BASE-01 h6 against two available after h4 IN"]]
    table(child, "ItemTransfer")["instances"][0]["rows"][1][4] = 3
    return child


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "native-input.json"
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("frozen source differs")
    if not target.exists():
        target.write_bytes(raw)
    print(json.dumps({"sha256": sha(raw), "parent_sha256": PARENT_SHA}))


if __name__ == "__main__":
    main()
