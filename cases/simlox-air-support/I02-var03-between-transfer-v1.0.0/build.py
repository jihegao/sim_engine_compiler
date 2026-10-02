"""Freeze a scheduled BETWEEN transfer on the accepted I02.var01 IN case."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I02-var01-in-transfer-v1.0.2/native-input.json"
PARENT_SHA = "85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d"


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
    transfers = table(parent, "ItemTransfer")
    assert transfers["instances"][0]["rows"] == [
        ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None]]
    child = copy.deepcopy(parent)
    table(child, "ProblemDescription")["instances"][0]["rows"] = [
        ["I02.var03 BETWEEN one LRU DEPOT-01 to BASE-01 at h6 after accepted h4 IN"]]
    table(child, "ItemTransfer")["instances"][0]["rows"].append(
        ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None])
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
