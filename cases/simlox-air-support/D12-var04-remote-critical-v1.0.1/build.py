"""Freeze the local/remote critical-small PM comparison from accepted D12.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D12-var01-active-small-v1.0.0" / "linked-input.json"
parent_sha256 = "cddf59ab7d557f6c643138ce8241fa43d7d5a569396538a6934bf7de00b3ffd1"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == parent_sha256


def tab(tables, name):
    return tables[name]


def rows(table):
    assert len(table["instances"]) == 1, table["name"]
    return table["instances"][0]["rows"]


def cell(table, column, match_column, match_value, value):
    names = [c["name"] for c in table["columns"]]
    target = [r for r in rows(table) if r[names.index(match_column)] == match_value]
    assert len(target) == 1, (table["name"], match_column, match_value)
    target[0][names.index(column)] = value


def make(arm):
    doc = json.loads(parent.read_text(encoding="utf-8"))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(tables) == len(doc["model"]["tables"]) == 31
    cell(tab(tables, "ProblemDescription"), "PDESC", "PDESC", "D12.var01 linked active-small PM boundary", f"D12.var04 {arm} critical-small PM boundary")
    control = rows(tab(tables, "Control"))[0]
    control_columns = [c["name"] for c in tab(tables, "Control")["columns"]]
    assert control[control_columns.index("SIMPE")] == control[control_columns.index("RCEND")] == 60
    control[control_columns.index("SIMPE")] = 30
    control[control_columns.index("RCEND")] = 30
    for r in rows(tab(tables, "ResultCollection")):
        assert r[2:4] == [0, 60]
        r[3] = 30
    profiles = rows(tab(tables, "OperationProfile"))
    assert len(profiles) == 3 and [r[2] for r in profiles] == [8, 20, 32]
    profiles.pop()
    profiles.pop()

    station = tab(tables, "Station")
    base = rows(station)[0]
    assert base[0:4] == ["BASE-01", "Teaching base", 1, "WS"]
    remote = base.copy()
    remote[0:2] = ["BASE-02", "Remote PM base"]
    rows(station).append(remote)
    structure = tab(tables, "StationStructure")
    assert rows(structure) == []
    rows(structure).append(["BASE-01", "BASE-02", 0.25, 0.25, None, None, 1, "SLOW", None, None, None])
    allocation = tab(tables, "ResourceAllocation")
    assert rows(allocation) == [["AIR_BASIC", "P-MAINT", "BASE-01", 1, None]]
    rows(allocation)[0][3] = 2
    rows(allocation).append(["AIR_BASIC", "P-MAINT", "BASE-02", 2, None])

    pm = tab(tables, "MaterielPM")
    cell(pm, "DTIM", "PMID", "CAL24", 0)
    cell(pm, "PMID", "PMID", "BIG48P5", "BIG24P75")
    cell(pm, "DESCR", "PMID", "BIG24P75", "24.75-hour larger service")
    cell(pm, "PMINT", "PMID", "BIG24P75", 24.75)
    cell(pm, "DTIM", "PMID", "BIG24P75", 0.5)
    pm_location = tab(tables, "PMLocation")
    cell(pm_location, "PMID", "PMID", "BIG48P5", "BIG24P75")
    if arm == "remote":
        cell(pm_location, "STID", "PMID", "CAL24", "BASE-02")
    for name in ("Tasks", "TaskBreakDown", "SubTaskResource"):
        cell(tab(tables, name), "TID", "TID", "PM-BIG48P5", "PM-BIG24P75")
    cell(pm_location, "TID", "PMID", "BIG24P75", "PM-BIG24P75")

    output = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == output, f"frozen {arm} source differs"
    else:
        target.write_bytes(output)
    return hashlib.sha256(output).hexdigest()


if __name__ == "__main__":
    for arm in ("local", "remote"):
        print(arm, make(arm))
