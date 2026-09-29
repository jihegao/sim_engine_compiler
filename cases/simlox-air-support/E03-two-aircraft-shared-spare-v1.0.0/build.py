"""Derive a two-aircraft, one-spare local competition case from accepted E02."""
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


def update_one(t: dict, **values: object) -> None:
    names = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(names) or set(values) - set(names):
        raise ValueError(f"unexpected {t['name']} shape")
    for name, value in values.items():
        rows[0][names.index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted E02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    update_one(table(model, "ProblemDescription"), PDESC="E03 two aircraft compete for one local spare; second demand waits for repair")
    update_one(table(model, "System"), FRT=3000000)
    update_one(table(model, "Item"), FRT=3000000)
    update_one(table(model, "SystemDeployment"), QTYPS=2)
    update_one(table(model, "ItemRepair"), DIRPT=4.0)
    update_one(table(model, "StockAllocation"), STSIZ=1)
    profile = table(model, "OperationProfile")
    names = [c["name"] for c in profile["columns"]]
    rows = profile["instances"][0]["rows"]
    if len(rows) != 3 or [row[names.index("STIM")] for row in rows] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected parent mission schedule")
    rows[:] = [rows[0]]
    rows[0][names.index("IQTY")] = 2
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
        raise ValueError("frozen E03 input differs from generator")
    print(json.dumps({"case_id": "E03", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
