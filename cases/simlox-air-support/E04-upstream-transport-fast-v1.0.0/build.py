"""Derive a FAST upstream-stock transport case from accepted E02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E02-zero-stock-local-backorder-v1.0.0" / "native-input.json"
PARENT_SHA256 = "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table/instance")
    return found[0]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def update_one(t: dict, **values: object) -> None:
    names = [c["name"] for c in t["columns"]]
    data = rows(t)
    if len(data) != 1 or len(data[0]) != len(names) or set(values) - set(names):
        raise ValueError(f"unexpected {t['name']} shape")
    for name, value in values.items():
        data[0][names.index(name)] = value


def add_row(t: dict, **values: object) -> None:
    names = [c["name"] for c in t["columns"]]
    if set(values) - set(names):
        raise ValueError(f"unknown {t['name']} fields")
    rows(t).append([values.get(name) for name in names])


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted E02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    update_one(table(model, "ProblemDescription"), PDESC="E04 base shortage served from one upstream stock point over two-hour FAST shipment")
    add_row(table(model, "Station"), STID="DEPOT-01", DESCR="Teaching support depot", QTY=1, TYPE="WS")
    add_row(table(model, "StationStructure"), STID="BASE-01", MSTID="DEPOT-01", TFRMS=2.0, TTOMS=2.0, DFRAC=1.0, OPOL="FAST")
    update_one(table(model, "ItemRepair"), STID="DEPOT-01")
    add_row(table(model, "StockAllocation"), POINT="AIR_BASIC", IID="TEACH-LRU-01", STID="DEPOT-01", STSIZ=1)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUTPUT}")
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen E04 input differs from generator")
    print(json.dumps({"case_id": "E04", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
