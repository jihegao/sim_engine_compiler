"""Check the complete seed-1 model delta against the accepted E06 parent."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E06-var01-repair-routing-v1.0.0" / "upstream-input.json"
SAMPLE = HERE / "seed-01-input.json"
PARENT_SHA = "7febb8c32afaa24fbf3bad94ba240e53236d8967c6fe6df51b4cfb7686828b0d"
SAMPLE_SHA = "c1b0d9c49af16f1cd9bf41d8ee8b38bb6599952df1a6f3e2461c89d6bd3cc112"


def table(doc: dict, name: str) -> dict:
    matches = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise AssertionError(f"ambiguous table {name}")
    return matches[0]


def rows(doc: dict, name: str) -> list:
    return table(doc, name)["instances"][0]["rows"]


def set_cell(doc: dict, name: str, row: int, column: str, old: object, new: object) -> None:
    item = table(doc, name)
    index = [col["name"] for col in item["columns"]].index(column)
    if rows(doc, name)[row][index] != old:
        raise AssertionError(f"unexpected parent {name}[{row}].{column}")
    rows(doc, name)[row][index] = new


def main() -> None:
    parent_raw, sample_raw = PARENT.read_bytes(), SAMPLE.read_bytes()
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise AssertionError("parent SHA-256 differs")
    if hashlib.sha256(sample_raw).hexdigest() != SAMPLE_SHA:
        raise AssertionError("seed-1 sample SHA-256 differs")
    expected, actual = copy.deepcopy(json.loads(parent_raw)), json.loads(sample_raw)
    set_cell(expected, "ProblemDescription", 0, "PDESC",
             "E06 cumulative direct-repair boundary upstream",
             "E06 three-level cumulative direct repair fractions 0.2/0.7/1")
    set_cell(expected, "Control", 0, "SIMPE", 36.0, 60.0)
    set_cell(expected, "Control", 0, "RCEND", 36.0, 60.0)
    for index in range(2):
        set_cell(expected, "ResultCollection", index, "RCEND", 36.0, 60.0)
    set_cell(expected, "ItemRepair", 0, "DIRPF", 0.0, 0.2)
    set_cell(expected, "ItemRepair", 1, "DIRPF", 1.0, 0.7)
    station = rows(expected, "Station")
    if len(station) != 2:
        raise AssertionError("parent station count")
    new_station = copy.deepcopy(station[1])
    new_station[0:2] = ["WORKSHOP-01", "Teaching final repair workshop"]
    station.append(new_station)
    structure = rows(expected, "StationStructure")
    if len(structure) != 1:
        raise AssertionError("parent support link count")
    new_link = copy.deepcopy(structure[0])
    new_link[0:2] = ["DEPOT-01", "WORKSHOP-01"]
    structure.append(new_link)
    repair = rows(expected, "ItemRepair")
    if len(repair) != 2:
        raise AssertionError("parent repair count")
    new_repair = copy.deepcopy(repair[1])
    new_repair[1], new_repair[4] = "WORKSHOP-01", 1.0
    repair.append(new_repair)
    stock = rows(expected, "StockAllocation")
    if len(stock) != 2:
        raise AssertionError("parent stock count")
    new_stock = copy.deepcopy(stock[1])
    new_stock[2] = "WORKSHOP-01"
    stock.append(new_stock)
    if expected != actual:
        raise AssertionError("seed-1 model contains an unlisted delta")
    print(json.dumps({"schema": "simlox-e06-three-level-exact-delta/v1", "passed": True,
                      "parent_sha256": PARENT_SHA, "sample_sha256": SAMPLE_SHA,
                      "changed_existing_cells": 7, "appended_rows": 4,
                      "populated_tables": sum(bool(t["instances"][0]["rows"]) for t in actual["model"]["tables"])}))


if __name__ == "__main__":
    main()
