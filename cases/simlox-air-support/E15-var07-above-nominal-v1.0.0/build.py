"""Freeze E15.var07 above-nominal ISTOH from the accepted tracked E15 parent."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-default.json"
PARENT_SHA = "602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected exactly one {name} instance")
    return matches[0]


def change(t: dict, row: int, column: str, before: object, after: object) -> None:
    names = [c["name"] for c in t["columns"]]
    index = names.index(column)
    cells = t["instances"][0]["rows"][row]
    if cells[index] != before:
        raise ValueError(f"unexpected parent {t['name']}.{column}")
    cells[index] = after


def build() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted E15 tracked parent fingerprint differs")
    doc = copy.deepcopy(json.loads(PARENT.read_bytes()))
    model = doc["model"]
    change(table(model, "ProblemDescription"), 0, "PDESC", "E15.var07 tracked stock reorder initial depot on-hand default", "E15.var07 explicit depot ISTOH6 above nominal STSIZ4")
    item = table(model, "Item")
    columns = [c["name"] for c in item["columns"]]
    assert item["instances"][0]["rows"][0][columns.index("TRACK")] == "Y"
    stock = table(model, "StockAllocation")
    names = [c["name"] for c in stock["columns"]]
    rows = stock["instances"][0]["rows"]
    depot = [i for i, row in enumerate(rows) if row[names.index("IID")] == "TEACH-DU-01" and row[names.index("STID")] == "DEPOT-01"]
    if len(depot) != 1 or rows[depot[0]][names.index("STSIZ")] != 4 or rows[depot[0]][names.index("ROSIZ")] != 2:
        raise ValueError("unexpected parent depot stock policy")
    change(stock, depot[0], "ISTOH", None, 6)
    return doc


def main() -> None:
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


if __name__ == "__main__":
    main()
