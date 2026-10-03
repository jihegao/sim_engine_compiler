"""Freeze a two-item traditional-failure robbing feasibility probe from E03."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E03-two-aircraft-shared-spare-v1.0.0/native-input.json"
PARENT_SHA = "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"


def rows(doc: dict, name: str) -> tuple[list[str], list[list]]:
    tables = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(tables) == 1 and len(tables[0]["instances"]) == 1, name
    t = tables[0]
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    rows(doc, "ProblemDescription")[1][0][0] = "E13 diagnostic: two traditional LRUs, no spares, robbing enabled"
    cn, control = rows(doc, "Control")
    assert control[0][cn.index("ENROB")] is None and control[0][cn.index("RSEED")] == "1"
    control[0][cn.index("ENROB")] = "Y"
    sn, systems = rows(doc, "System")
    assert len(systems) == 1 and systems[0][sn.index("FRT")] == 3000000
    systems[0][sn.index("FRT")] = 6000000
    names, items = rows(doc, "Item")
    assert len(items) == 1 and items[0][names.index("IID")] == "TEACH-LRU-01" and items[0][names.index("ENROB")] is None
    second = items[0].copy()
    second[names.index("IID")] = "TEACH-LRU-02"
    second[names.index("DESCR")] = "Second traditional replaceable teaching component"
    items.append(second)
    names, structure = rows(doc, "ItemStructure")
    assert len(structure) == 1 and structure[0][names.index("IID")] == "TEACH-LRU-01"
    second = structure[0].copy()
    second[names.index("IID")] = "TEACH-LRU-02"
    structure.append(second)
    names, repairs = rows(doc, "ItemRepair")
    assert len(repairs) == 1 and repairs[0][names.index("DIRPT")] == 4.0
    second = repairs[0].copy()
    second[names.index("IID")] = "TEACH-LRU-02"
    second[names.index("DIRPT")] = 12.0
    repairs.append(second)
    names, stock = rows(doc, "StockAllocation")
    assert len(stock) == 1 and stock[0][names.index("IID")] == "TEACH-LRU-01" and stock[0][names.index("STSIZ")] == 1
    stock[0][names.index("STSIZ")] = 0
    second = stock[0].copy()
    second[names.index("IID")] = "TEACH-LRU-02"
    stock.append(second)
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    output = HERE / "native-input.json"
    raw = build()
    if sys.argv[1:] == ["--write"]:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: build.py [--write]")
    else:
        assert output.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())
