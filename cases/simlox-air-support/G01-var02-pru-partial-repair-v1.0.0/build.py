"""Derive a primary partially repairable unit from the accepted DU topology."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var03-du-discard-reorder-v1.0.0" / "native-input.json"
PARENT_SHA = "c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def columns(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def set_field(t: dict, row: list, field: str, value: object) -> None:
    row[columns(t).index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted DU parent input changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    old = "TEACH-DU-01"
    new = "TEACH-PRU-01"
    for name, field in (("Item", "IID"), ("ItemStructure", "IID"),
                        ("ItemReorder", "IID"), ("StockAllocation", "IID")):
        t = table(model, name)
        matching = [r for r in rows(t) if r[columns(t).index(field)] == old]
        if len(matching) != (2 if name == "StockAllocation" else 1):
            raise ValueError(f"unexpected {name} parent rows")
        for row in matching:
            set_field(t, row, field, new)
    set_field(table(model, "ProblemDescription"), rows(table(model, "ProblemDescription"))[0],
              "PDESC", "G01.var02 primary PRU partial repair and depot reorder")
    item = table(model, "Item")
    set_field(item, rows(item)[0], "TYPE", "PRU")
    set_field(item, rows(item)[0], "DESCR", "Partially repairable primary teaching component")
    repair = table(model, "ItemRepair")
    if rows(repair):
        raise ValueError("parent repair table is not empty")
    values = {"IID": new, "STID": "DEPOT-01", "DIRPT": 1.0, "SURPT": 0.0,
              "DIRPF": 0.5, "SURPF": 1.0}
    rows(repair).append([values.get(name) for name in columns(repair)])
    reorder = table(model, "ItemReorder")
    set_field(reorder, rows(reorder)[0], "DISCF", 0.5)
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
