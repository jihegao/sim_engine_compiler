"""Derive a per-index similar-item stockout from the reviewed G01.var06 branch."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var06-similar-vs-identical-v1.0.1/native-similar.json"
PARENT_SHA = "65f0d216cf30dddbda24d9a58617ef5049ccd520891363c6b3bba06161f6c472"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unique_row(doc: dict, table_name: str, key: str, value: object) -> tuple[list[str], list]:
    tables = [t for t in doc["model"]["tables"] if t["name"] == table_name]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError(f"one {table_name} table/instance required")
    t = tables[0]
    names = [c["name"] for c in t["columns"]]
    found = [r for r in t["instances"][0]["rows"] if r[names.index(key)] == value]
    if len(found) != 1:
        raise ValueError(f"one {table_name} row for {key}={value} required")
    return names, found[0]


def build() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("G01.var06 similar parent changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    names, row = unique_row(doc, "ProblemDescription", "PDESC", "G01.var06 similar: two one-aircraft LRU positions, matched rate and local stock")
    row[names.index("PDESC")] = "G01.var06 indexed stockout: index 1 shortage while index 0 retains one spare"
    names, row = unique_row(doc, "ItemRepair", "IID", "TEACH-LRU-01")
    if row[names.index("DIRPT")] != 1.0:
        raise ValueError("unexpected parent direct repair time")
    row[names.index("DIRPT")] = 30.0
    names, row = unique_row(doc, "StockAllocation", "IID", "TEACH-LRU-01")
    if row[names.index("STSIZ")] != 2:
        raise ValueError("unexpected parent stock")
    row[names.index("STSIZ")] = 1
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
        raise ValueError("frozen stockout input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
