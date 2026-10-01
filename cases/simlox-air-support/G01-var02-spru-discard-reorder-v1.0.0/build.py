"""Derive a secondary partially repairable unit from accepted DP topology."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var03-dp-discard-reorder-v1.0.0/native-input.json"
PARENT_SHA = "a51598aed393f01fa4a6e28103ee4eed8aadec53114e3ed72e466f4a5126f226"
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


def cols(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def set_field(t: dict, row: list, field: str, value: object) -> None:
    row[cols(t).index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted DP parent input changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    old, new = "TEACH-SRU-01", "TEACH-SPRU-01"
    found_in = []
    for t in model["tables"]:
        count = 0
        for row in rows(t):
            for i, value in enumerate(row):
                if value == old:
                    row[i] = new
                    count += 1
        if count:
            found_in.append(t["name"])
    expected = ["Item", "ItemStructure", "ItemReplacement", "ItemReorder", "StockAllocation"]
    if sorted(found_in) != sorted(expected):
        raise ValueError(f"unexpected DP identity references: {found_in}")
    set_field(table(model, "ProblemDescription"), rows(table(model, "ProblemDescription"))[0],
              "PDESC", "G01.var02 nested SPRU partial repair and depot reorder")
    item = table(model, "Item")
    target = [row for row in rows(item) if row[cols(item).index("IID")] == new]
    if len(target) != 1:
        raise ValueError("one secondary item required")
    set_field(item, target[0], "TYPE", "SPRU")
    set_field(item, target[0], "DESCR", "Partially repairable secondary item inside teaching LRU")
    repair = table(model, "ItemRepair")
    if any(row[cols(repair).index("IID")] == new for row in rows(repair)):
        raise ValueError("unexpected secondary repair row")
    values = {"IID": new, "STID": "DEPOT-01", "DIRPT": 1.0, "SURPT": 0.0,
              "DIRPF": 0.5, "SURPF": 1.0}
    rows(repair).append([values.get(name) for name in cols(repair)])
    reorder = table(model, "ItemReorder")
    target = [row for row in rows(reorder) if row[cols(reorder).index("IID")] == new]
    if len(target) != 1:
        raise ValueError("one secondary reorder row required")
    set_field(reorder, target[0], "DISCF", 0.5)
    set_field(table(model, "Control"), rows(table(model, "Control"))[0], "RSEED", "7")
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
