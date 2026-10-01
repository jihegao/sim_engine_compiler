"""Derive the first traditional LRU/SRU repair chain from accepted E01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0" / "native-input.json"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def names(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def add(t: dict, **values: object) -> None:
    columns = names(t)
    if set(values) - set(columns):
        raise ValueError(f"unknown {t['name']} field")
    rows(t).append([values.get(name) for name in columns])


def set_field(t: dict, row: list, field: str, value: object) -> None:
    row[names(t).index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted E01 input changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    set_field(table(model, "ProblemDescription"), rows(table(model, "ProblemDescription"))[0], "PDESC", "G01.var01 traditional LRU/SRU chain with local replacements")
    item = table(model, "Item")
    if len(rows(item)) != 1 or rows(item)[0][names(item).index("IID")] != "TEACH-LRU-01":
        raise ValueError("unexpected E01 item")
    add(item, IID="TEACH-SRU-01", DESCR="Repairable subitem inside teaching LRU", FRT=300000, OPID="OPHOURS", TYPE="SRU", CRIT=1.0)
    add(table(model, "ItemStructure"), IID="TEACH-SRU-01", MID="TEACH-LRU-01", QTYPM=1, ENVF=1.0)
    repair = table(model, "ItemRepair")
    set_field(repair, rows(repair)[0], "SURPT", 1.5)
    add(repair, IID="TEACH-SRU-01", STID="BASE-01", DIRPT=1.0, SURPT=0.0, DIRPF=1.0, SURPF=1.0)
    add(table(model, "ItemReplacement"), MID="TEACH-LRU-01", IID="TEACH-SRU-01", STID="BASE-01", SURPT=0.75, SURPF=1.0)
    add(table(model, "StockAllocation"), POINT="AIR_BASIC", IID="TEACH-SRU-01", STID="BASE-01", STSIZ=1)
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
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
