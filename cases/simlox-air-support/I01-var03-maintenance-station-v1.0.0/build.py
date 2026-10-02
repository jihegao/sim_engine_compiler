"""Freeze a two-station maintenance POINT contrast from accepted I01.var01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var01-two-stock-points-v1.0.0/stocked-input.json"
PARENT_SHA = "9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb"
E04_DONOR = HERE.parent / "E04-upstream-transport-fast-v1.0.0/native-input.json"
E04_DONOR_SHA = "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1, name
    return matches[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def named_row(t: dict, values: dict) -> list:
    names = [c["name"] for c in t["columns"]]
    assert not (values.keys() - set(names)), (t["name"], values)
    return [values.get(name) for name in names]


def new_table(name: str, columns: list[tuple[str, str, bool]], data: list[list]) -> dict:
    assert all(len(row) == len(columns) for row in data)
    return {"columns": [dict(datatype=kind, name=column, **({"key": True} if key else {}))
                        for column, kind, key in columns],
            "instances": [{"instance_name": "", "rows": data}], "name": name}


def build() -> tuple[dict, dict]:
    parent_raw, donor_raw = PARENT.read_bytes(), E04_DONOR.read_bytes()
    assert digest(parent_raw) == PARENT_SHA, "accepted stock parent changed"
    assert digest(donor_raw) == E04_DONOR_SHA, "accepted station donor changed"
    parent, donor = json.loads(parent_raw), json.loads(donor_raw)
    assert rows(parent, "StationStructure") == []
    assert rows(parent, "ItemRepair") == [["TEACH-LRU-01", "BASE-01", 1.0, 0.0,
                                           1.0, 1.0] + [None] * 10]
    assert rows(parent, "StockAllocation") == [
        ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 1] + [None] * 5,
        ["AIR_EMPTY", "TEACH-LRU-01", "BASE-01", 0] + [None] * 5]
    assert rows(donor, "Station")[1][:4] == ["DEPOT-01", "Teaching support depot", 1, "WS"]
    assert rows(donor, "StationStructure") == [["BASE-01", "DEPOT-01", 2.0, 2.0,
                                                None, None, 1.0, "FAST", None, None, None]]
    common = copy.deepcopy(parent)
    rows(common, "Station").append(copy.deepcopy(rows(donor, "Station")[1]))
    rows(common, "StationStructure").append(copy.deepcopy(rows(donor, "StationStructure")[0]))
    base_repair = rows(common, "ItemRepair")[0]
    base_repair[11] = "I01-LRU-DIRP"
    depot_repair = copy.deepcopy(base_repair)
    depot_repair[1] = "DEPOT-01"
    rows(common, "ItemRepair").append(depot_repair)
    rows(common, "Tasks").append(
        ["I01-LRU-DIRP", "Direct failed-LRU repair", "LRU-CM", "BASE", None])
    common["model"]["tables"].extend([
        new_table("TaskCategory", [("TCID", "string", True), ("DESCR", "string", False),
                                   ("NOTE", "string", False)],
                  [["LRU-CM", "LRU corrective maintenance", None]]),
        new_table("TaskLevel", [("TLID", "string", True), ("LEVL", "integer", False),
                                ("NOTE", "string", False)], [["BASE", 1, None]]),
        new_table("MaintenanceAllocation", [("POINT", "string", True), ("TCID", "string", True),
                                             ("TLID", "string", True), ("STID", "string", True),
                                             ("NOTE", "string", False)],
                  [["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
                   ["AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01", None]])])
    rows(common, "StockAllocation")[:] = [
        [point, "TEACH-LRU-01", station, size, None, None, None, None, None]
        for point in ("AIR_BASIC", "AIR_DEPOT")
        for station, size in (("BASE-01", 1), ("DEPOT-01", 0))]
    base = copy.deepcopy(common)
    rows(base, "ProblemDescription")[0][0] = "I01.var03 maintenance POINT repairs LRU at BASE-01"
    depot = copy.deepcopy(common)
    rows(depot, "Control")[0][3] = "AIR_DEPOT"
    rows(depot, "ProblemDescription")[0][0] = "I01.var03 maintenance POINT routes LRU repair to DEPOT-01"
    return base, depot


def main() -> None:
    for name, doc in zip(("base-input.json", "depot-input.json"), build()):
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen source differs: {name}")
        if not path.exists():
            path.write_bytes(raw)
        print(name, digest(raw))


if __name__ == "__main__":
    main()
