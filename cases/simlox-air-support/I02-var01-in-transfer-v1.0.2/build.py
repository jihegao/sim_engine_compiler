"""Freeze a single scheduled IN transfer on the accepted E04 FAST model."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json"
PARENT_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"


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
    assert all(item["name"] != "ItemTransfer" for item in parent["model"]["tables"])
    assert table(parent, "StockAllocation")["instances"][0]["rows"] == [
        ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 0, None, None, None, None, None],
        ["AIR_BASIC", "TEACH-LRU-01", "DEPOT-01", 1, None, None, None, None, None]]
    child = copy.deepcopy(parent)
    table(child, "ProblemDescription")["instances"][0]["rows"] = [
        ["I02.var01 IN one LRU to DEPOT-01 at h4 with tracked item report"]]
    item = table(child, "Item")
    item_names = [column["name"] for column in item["columns"]]
    assert item_names.count("TRACK") == 1
    item_rows = item["instances"][0]["rows"]
    assert len(item_rows) == 1 and item_rows[0][item_names.index("TRACK")] is None
    item_rows[0][item_names.index("TRACK")] = "Y"
    results = table(child, "ResultCollection")["instances"][0]["rows"]
    assert results == [["MISSION", 0.5, 0, 36.0, None, None],
                       ["SYSTEM", 0.5, 0, 36.0, None, None]]
    results.append(["ITEM", 0.5, 0, 36.0, None, None])
    columns = [
        {"name": "STFID", "datatype": "string", "key": True},
        {"name": "STTID", "datatype": "string", "key": True},
        {"name": "IID", "datatype": "string", "key": True},
        {"name": "TFTIME", "datatype": "double", "key": True},
        {"name": "TFQTY", "datatype": "integer"},
        {"name": "TFDT", "datatype": "double"},
        {"name": "NOTE", "datatype": "string"},
    ]
    child["model"]["tables"].append({
        "name": "ItemTransfer", "columns": columns,
        "instances": [{"instance_name": "", "rows": [
            ["<OUTSIDE>", "DEPOT-01", "TEACH-LRU-01", 4.0, 1, 0.0, None]]}],
    })
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
