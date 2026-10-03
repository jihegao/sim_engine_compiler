"""Derive a physical ASSY wrapper from accepted F01.var01 repeated LRU/SRU chain."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F01-var01-two-three-level-v1.0.1/three-level-input.json"
PARENT_SHA = "ae0181581822422aaf3c8bc5b7c0352c8bf31187178408e4f211102e438c77b5"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def names(t: dict) -> list[str]:
    return [col["name"] for col in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def add(t: dict, **values: object) -> None:
    cols = names(t)
    if set(values) - set(cols):
        raise ValueError(f"unknown {t['name']} field")
    rows(t).append([values.get(name) for name in cols])


def build() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted F01.var01 parent changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    desc = table(doc, "ProblemDescription")
    rows(desc)[0][names(desc).index("PDESC")] = "F01.var02 structural ASSY wraps repeated-reissue LRU; direct system-to-LRU logistic replacement"
    item = table(doc, "Item")
    if {row[names(item).index("IID")] for row in rows(item)} != {"TEACH-LRU-01", "TEACH-SRU-01"}:
        raise ValueError("unexpected parent items")
    add(item, IID="TEACH-ASSY-01", DESCR="Structural assembly around teaching LRU", TYPE="ASSY")
    structure = table(doc, "ItemStructure")
    lru = [row for row in rows(structure) if row[names(structure).index("IID")] == "TEACH-LRU-01"]
    if len(lru) != 1 or lru[0][names(structure).index("MID")] != "TEACH-AIR-01":
        raise ValueError("unexpected system-to-LRU parent link")
    lru[0][names(structure).index("MID")] = "TEACH-ASSY-01"
    add(structure, IID="TEACH-ASSY-01", MID="TEACH-AIR-01", QTYPM=1, ENVF=1.0)
    replacement = table(doc, "ItemReplacement")
    add(replacement, MID="TEACH-AIR-01", IID="TEACH-LRU-01", STID="BASE-01", SURPT=0.5, SURPF=1.0, SURPTID="E01-SURP")
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
