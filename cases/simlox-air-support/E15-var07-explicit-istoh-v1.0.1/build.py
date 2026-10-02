"""Freeze an E15 stock-based reorder pair from the accepted G01 DU donor."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DONOR = HERE.parent / "G01-var03-du-discard-reorder-v1.0.0" / "native-input.json"
DONOR_SHA = "c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9"
ARMS = {"default": None, "explicit-three": 3}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} instance")
    return matches[0]


def row_dicts(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row)) for row in t["instances"][0]["rows"]]


def set_cell(t: dict, row_index: int, column: str, value: object) -> None:
    names = [c["name"] for c in t["columns"]]
    t["instances"][0]["rows"][row_index][names.index(column)] = value


def build(arm: str) -> dict:
    if arm not in ARMS or sha(DONOR) != DONOR_SHA:
        raise ValueError("unknown arm or accepted donor fingerprint differs")
    doc = copy.deepcopy(json.loads(DONOR.read_bytes()))
    model = doc["model"]
    desc = table(model, "ProblemDescription")
    set_cell(desc, 0, "PDESC", f"E15.var07 tracked stock reorder initial depot on-hand {arm}")
    item = table(model, "Item")
    item_rows = row_dicts(item)
    if len(item_rows) != 1 or item_rows[0]["IID"] != "TEACH-DU-01" or item_rows[0]["TRACK"] is not None:
        raise ValueError("unexpected accepted donor item tracking")
    set_cell(item, 0, "TRACK", "Y")
    stock = table(model, "StockAllocation")
    rows = row_dicts(stock)
    depot = [i for i, row in enumerate(rows) if row["IID"] == "TEACH-DU-01" and row["STID"] == "DEPOT-01"]
    if len(depot) != 1 or rows[depot[0]]["STSIZ"] != 2 or rows[depot[0]]["ROSIZ"] != 1:
        raise ValueError("unexpected accepted donor stock solution")
    set_cell(stock, depot[0], "STSIZ", 4)
    set_cell(stock, depot[0], "ROSIZ", 2)
    set_cell(stock, depot[0], "ISTOH", ARMS[arm])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        path = HERE / f"native-input-{arm}.json"
        raw = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {arm}")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"donor_sha256": DONOR_SHA, "arm_sha256": result}, indent=2))


if __name__ == "__main__":
    main()
