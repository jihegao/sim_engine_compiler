"""Derive a one-LRU replacement and local item-repair D01 slice."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA256 = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return matches[0]


def fields(t: dict) -> list[str]:
    return [column["name"] for column in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def update(t: dict, **values: object) -> None:
    if len(rows(t)) != 1 or len(rows(t)[0]) != len(fields(t)) or set(values) - set(fields(t)):
        raise ValueError(f"unexpected {t['name']} shape or fields")
    for key, value in values.items():
        rows(t)[0][fields(t).index(key)] = value


def make_row(t: dict, **values: object) -> list:
    if set(values) - set(fields(t)):
        raise ValueError(f"unknown {t['name']} columns")
    return [values.get(field) for field in fields(t)]


def add_one(model: dict, name: str, **values: object) -> None:
    t = table(model, name)
    if rows(t):
        raise ValueError(f"parent {name} not empty")
    rows(t).append(make_row(t, **values))


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted D01 system-direct parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    update(table(model, "ProblemDescription"), PDESC="D01 installed LRU: one local spare, system replacement, direct item repair")
    add_one(model, "Item", IID="TEACH-LRU-01", DESCR="Single replaceable teaching component", FRT=300000, OPID="OPHOURS", TYPE="LRU", CRIT=1.0)
    add_one(model, "ItemStructure", IID="TEACH-LRU-01", MID="TEACH-AIR-01", QTYPM=1, ENVF=1.0)
    update(table(model, "SystemRepair"), DIRPT=0.0, SURPT=0.5, DIRPF=1.0, SURPF=1.0)
    add_one(model, "ItemRepair", IID="TEACH-LRU-01", STID="BASE-01", DIRPT=1.0, SURPT=0.0, DIRPF=1.0, SURPF=1.0)
    add_one(model, "StockAllocation", POINT="AIR_BASIC", IID="TEACH-LRU-01", STID="BASE-01", STSIZ=1)
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
        raise ValueError("frozen input differs from generator")
    print(json.dumps({"case_id": "D01", "variant": "installed-lru-local-repair", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
