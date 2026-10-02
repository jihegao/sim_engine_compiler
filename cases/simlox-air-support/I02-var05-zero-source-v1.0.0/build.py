"""Freeze matched h2 BETWEEN arms differing only in initial depot stock."""
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
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1
    return matches[0]


def build() -> tuple[dict, dict]:
    source = PARENT.read_bytes()
    assert sha(source) == PARENT_SHA
    accepted = json.loads(source)
    assert table(accepted, "ItemTransfer")["instances"][0]["rows"] == [
        ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None],
        ["DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None]]
    assert table(accepted, "StockAllocation")["instances"][0]["rows"] == [
        ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 0, None, None, None, None, None],
        ["AIR_BASIC", "TEACH-LRU-01", "DEPOT-01", 1, None, None, None, None, None]]
    control = copy.deepcopy(accepted)
    table(control, "ItemTransfer")["instances"][0]["rows"][1][3] = 2.0
    table(control, "ProblemDescription")["instances"][0]["rows"] = [
        ["I02.var05 control h2 BETWEEN one LRU with depot initial stock one before h4 IN"]]
    child = copy.deepcopy(control)
    table(child, "StockAllocation")["instances"][0]["rows"][1][3] = 0
    table(child, "ProblemDescription")["instances"][0]["rows"] = [
        ["I02.var05 zero-source h2 BETWEEN one LRU with depot initial stock zero before h4 IN"]]
    return control, child


def main() -> None:
    for name, doc in zip(("control-input.json", "native-input.json"), build(), strict=True):
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} differs")
        if not path.exists():
            path.write_bytes(raw)
        print(json.dumps({"file": name, "sha256": sha(raw), "parent_sha256": PARENT_SHA}))


if __name__ == "__main__":
    main()
