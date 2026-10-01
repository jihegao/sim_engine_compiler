"""Derive a QTYPM=2 versus NSIMI=2 pair from accepted E01 without subitems."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
OUTPUTS = {"identical": HERE / "native-identical.json", "similar": HERE / "native-similar.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def unique_row(t: dict, key: str, value: object) -> tuple[list[str], list]:
    names = [c["name"] for c in t["columns"]]
    found = [r for r in t["instances"][0]["rows"] if r[names.index(key)] == value]
    if len(found) != 1:
        raise ValueError(f"one {t['name']} row for {key}={value} required")
    return names, found[0]


def build(kind: str) -> dict:
    if kind not in OUTPUTS or sha(PARENT) != PARENT_SHA:
        raise ValueError("kind or accepted E01 parent changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    names, row = unique_row(table(doc, "ProblemDescription"), "PDESC", "E01 local spare: explicit 10-minute REMOVE and 20-minute REPLACE")
    row[names.index("PDESC")] = f"G01.var06 {kind}: two one-aircraft LRU positions, matched rate and local stock"
    names, row = unique_row(table(doc, "System"), "SID", "TEACH-AIR-01")
    if row[names.index("FRT")] != 300000:
        raise ValueError("unexpected parent system rate")
    row[names.index("FRT")] = 600000
    names, row = unique_row(table(doc, "Item"), "IID", "TEACH-LRU-01")
    if row[names.index("NSIMI")] is not None or row[names.index("FRT")] != 300000:
        raise ValueError("unexpected parent item")
    if kind == "similar":
        row[names.index("NSIMI")] = 2
    names, row = unique_row(table(doc, "ItemStructure"), "IID", "TEACH-LRU-01")
    if row[names.index("MID")] != "TEACH-AIR-01" or row[names.index("QTYPM")] != 1:
        raise ValueError("unexpected parent item structure")
    if kind == "identical":
        row[names.index("QTYPM")] = 2
    names, row = unique_row(table(doc, "StockAllocation"), "IID", "TEACH-LRU-01")
    if row[names.index("STSIZ")] != 1:
        raise ValueError("unexpected parent stock")
    row[names.index("STSIZ")] = 2
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {"parent_sha256": PARENT_SHA, "variants": {}}
    for kind, path in OUTPUTS.items():
        raw = (json.dumps(build(kind), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {kind} input differs from builder")
        result["variants"][kind] = {"input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
