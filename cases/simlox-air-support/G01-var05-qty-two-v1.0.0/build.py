"""Derive two interchangeable installed LRUs from accepted G01.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var01-lru-sru-v1.0.1/native-input.json"
PARENT_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def row(t: dict) -> tuple[list[str], list]:
    names = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"one {t['name']} row required")
    return names, rows[0]


def set_one(t: dict, key: str, value: object) -> None:
    names, values = row(t)
    values[names.index(key)] = value


def build() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted G01.var01 parent changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    set_one(table(doc, "ProblemDescription"), "PDESC", "G01.var05 two interchangeable LRU positions with matched system rate and ample local stock")
    system = table(doc, "System")
    names, values = row(system)
    if values[names.index("SID")] != "TEACH-AIR-01" or values[names.index("FRT")] != 300000:
        raise ValueError("unexpected parent system rate")
    set_one(system, "FRT", 600000)
    structure = table(doc, "ItemStructure")
    names = [c["name"] for c in structure["columns"]]
    lru = [r for r in structure["instances"][0]["rows"] if r[names.index("IID")] == "TEACH-LRU-01" and r[names.index("MID")] == "TEACH-AIR-01"]
    if len(lru) != 1 or lru[0][names.index("QTYPM")] != 1:
        raise ValueError("unexpected parent LRU quantity")
    lru[0][names.index("QTYPM")] = 2
    stock = table(doc, "StockAllocation")
    names = [c["name"] for c in stock["columns"]]
    lru_stock = [r for r in stock["instances"][0]["rows"] if r[names.index("IID")] == "TEACH-LRU-01"]
    if len(lru_stock) != 1 or lru_stock[0][names.index("STSIZ")] != 1:
        raise ValueError("unexpected parent LRU stock")
    lru_stock[0][names.index("STSIZ")] = 2
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
