"""Derive one discardable primary DU and depot reorder from accepted E01."""
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} instance")
    return matches[0]


def cols(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def add(t: dict, **fields: object) -> None:
    names = cols(t)
    if set(fields) - set(names):
        raise ValueError(f"invalid {t['name']} fields")
    rows(t).append([fields.get(name) for name in names])


def set_field(t: dict, row: list, field: str, value: object) -> None:
    row[cols(t).index(field)] = value


def build() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted E01 parent changed")
    doc = copy.deepcopy(json.loads(PARENT.read_bytes()))
    model = doc["model"]
    t = table(model, "ProblemDescription")
    set_field(t, rows(t)[0], "PDESC", "G01.var03 primary DU discard and depot reorder")
    item = table(model, "Item")
    if len(rows(item)) != 1 or rows(item)[0][cols(item).index("IID")] != "TEACH-LRU-01":
        raise ValueError("unexpected E01 item")
    set_field(item, rows(item)[0], "IID", "TEACH-DU-01")
    set_field(item, rows(item)[0], "TYPE", "DU")
    set_field(item, rows(item)[0], "DESCR", "Discardable primary teaching component")
    structure = table(model, "ItemStructure")
    set_field(structure, rows(structure)[0], "IID", "TEACH-DU-01")
    repair = table(model, "ItemRepair")
    if len(rows(repair)) != 1 or rows(repair)[0][cols(repair).index("IID")] != "TEACH-LRU-01":
        raise ValueError("unexpected E01 repair row")
    rows(repair).clear()
    add(table(model, "Station"), STID="DEPOT-01", DESCR="Teaching reorder depot", QTY=1, TYPE="DEPOT")
    add(table(model, "StationStructure"), STID="BASE-01", MSTID="DEPOT-01", TFRMS=2.0, TTOMS=2.0, DFRAC=1.0, OPOL="FAST")
    add(table(model, "ItemReorder"), IID="TEACH-DU-01", STID="DEPOT-01", LEADT=1.0)
    stock = table(model, "StockAllocation")
    set_field(stock, rows(stock)[0], "IID", "TEACH-DU-01")
    add(stock, POINT="AIR_BASIC", IID="TEACH-DU-01", STID="DEPOT-01", STSIZ=2, ROSIZ=1)
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))
