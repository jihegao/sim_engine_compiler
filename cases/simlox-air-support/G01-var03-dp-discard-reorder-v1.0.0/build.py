"""Build DP discard and depot reorder from accepted G01.var01."""
from __future__ import annotations

import copy
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var01-lru-sru-v1.0.1" / "native-input.json"
PARENT_SHA = "9c25a414615ac4ea523ee989385a913c692923e04bc41c6984b6866e86204bb9"
OUTPUT = HERE / "native-input.json"


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} instance")
    return matches[0]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def cols(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def add(t: dict, **fields: object) -> None:
    names = cols(t)
    if set(fields) - set(names):
        raise ValueError(f"invalid {t['name']} columns")
    rows(t).append([fields.get(name) for name in names])


def set_field(t: dict, row: list, field: str, value: object) -> None:
    row[cols(t).index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G01.var01 source changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    t = table(model, "ProblemDescription")
    set_field(t, rows(t)[0], "PDESC", "G01.var03 DP discarded after LRU repair and depot reorder")
    t = table(model, "Item")
    dp = next(r for r in rows(t) if r[cols(t).index("IID")] == "TEACH-SRU-01")
    set_field(t, dp, "TYPE", "DP")
    set_field(t, dp, "DESCR", "Discardable secondary item inside teaching LRU")
    t = table(model, "ItemRepair")
    rows(t)[:] = [r for r in rows(t) if r[cols(t).index("IID")] != "TEACH-SRU-01"]
    t = table(model, "Station")
    add(t, STID="DEPOT-01", DESCR="Teaching reorder depot", QTY=1, TYPE="DEPOT")
    add(table(model, "StationStructure"), STID="BASE-01", MSTID="DEPOT-01", TFRMS=2.0, TTOMS=2.0, DFRAC=1.0, OPOL="FAST")
    add(table(model, "ItemReorder"), IID="TEACH-SRU-01", STID="DEPOT-01", LEADT=1.0)
    add(table(model, "StockAllocation"), POINT="AIR_BASIC", IID="TEACH-SRU-01", STID="DEPOT-01", STSIZ=2, ROSIZ=1)
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    output = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(output)
    elif OUTPUT.read_bytes() != output:
        raise ValueError("frozen input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(output).hexdigest()}))
