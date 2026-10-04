"""Build a frozen two-SRU RRF/NFFF seed panel from accepted G01.var01."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "G01-var01-lru-sru-v1.0.1" / "native-input.json"
PARENT_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
SEEDS = range(2, 7)
ARMS = ("control", "extra")


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def table_map(doc: dict) -> dict[str, dict]:
    return {table["name"]: table for table in doc["model"]["tables"]}


def rows(table: dict) -> list[list]:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def col(table: dict, name: str) -> int:
    return [column["name"] for column in table["columns"]].index(name)


def duplicate(table: dict, id_field: str) -> None:
    original = rows(table)
    assert len(original) in (1, 2)
    source = next(row for row in original if row[col(table, id_field)] == "TEACH-SRU-01")
    peer = copy.deepcopy(source)
    peer[col(table, id_field)] = "TEACH-SRU-02"
    original.append(peer)


def build(seed: int, arm: str) -> dict:
    assert seed in SEEDS and arm in ARMS
    raw = PARENT.read_bytes()
    assert digest(raw) == PARENT_SHA
    doc = copy.deepcopy(json.loads(raw.decode("utf-8-sig")))
    tables = table_map(doc)
    item = tables["Item"]
    structure = tables["ItemStructure"]
    repair = tables["ItemRepair"]
    allocation = tables["StockAllocation"]
    replacement = tables["ItemReplacement"]
    duplicate(item, "IID")
    duplicate(structure, "IID")
    duplicate(repair, "IID")
    duplicate(allocation, "IID")
    duplicate(replacement, "IID")
    for row in rows(item):
        assert row[col(item, "TRACK")] is None
        row[col(item, "TRACK")] = "Y"
        if row[col(item, "IID")].startswith("TEACH-SRU-"):
            row[col(item, "FRT")] = 150000
    for row in rows(allocation):
        if row[col(allocation, "IID")].startswith("TEACH-SRU-"):
            row[col(allocation, "STSIZ")] = 4
    for row in rows(structure):
        if row[col(structure, "IID")].startswith("TEACH-SRU-"):
            row[col(structure, "RRF")] = 1.0 if arm == "control" else 4.0
            row[col(structure, "NFFF")] = 1.0 if arm == "control" else 2.0
            row[col(structure, "NFFT")] = 0.25
    rows(tables["Control"])[0][col(tables["Control"], "RSEED")] = str(seed)
    rows(tables["ProblemDescription"])[0][col(tables["ProblemDescription"], "PDESC")] = f"E14 two SRUs seed {seed} {arm} RRF/NFFF"
    collection = rows(tables["ResultCollection"])
    assert collection == [["MISSION", 0.5, 0, 36.0, None, None], ["SYSTEM", 0.5, 0, 36.0, None, None]]
    collection.append(["ITEM", 0.5, 0, 36.0, None, None])
    assert len(rows(item)) == 3 and len(rows(structure)) == 3
    assert len(rows(allocation)) == 3 and len(rows(replacement)) == 2
    return doc


def main() -> None:
    write = "--write" in sys.argv[1:]
    result = {}
    for seed in SEEDS:
        for arm in ARMS:
            name = f"seed{seed}-{arm}"
            payload = (json.dumps(build(seed, arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            path = CASE / f"{name}-input.json"
            if write:
                path.write_bytes(payload)
            else:
                assert path.read_bytes() == payload, f"frozen source changed: {name}"
            result[name] = digest(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
