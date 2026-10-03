"""Derive paired F02 fleet inputs from accepted D05 and five component cases."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES = {
    "D05": ("D05-maintenance-competition-v1.0.0/native-input.json", "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"),
    "F01": ("F01-var01-two-three-level-v1.0.1/three-level-input.json", "ae0181581822422aaf3c8bc5b7c0352c8bf31187178408e4f211102e438c77b5"),
    "A04": ("A04-two-day-formation-v1.0.0/native-input.json", "9e2eac17e0408903e099e6ce054ebf4b91db1ca79036afe29638ee8a41d40711"),
    "B04": ("B04-cross-midnight-turnround-v1.0.1/turnround-input.json", "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5"),
    "C03": ("C03-shared-crew-formation-v1.0.2/inputs/staffing-1.json", "159f5fa91d50afbd0d15840f8f007c62a3775d02d718152004017e20e545b789"),
    "E04": ("E04-upstream-transport-fast-v1.0.0/native-input.json", "2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [x for x in doc["model"]["tables"] if x["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return matches[0]


def columns(tab: dict) -> list[str]:
    return [c["name"] for c in tab["columns"]]


def rows(doc: dict, name: str) -> list[list[object]]:
    return table(doc, name)["instances"][0]["rows"]


def set_field(tab: dict, row: list[object], field: str, value: object) -> None:
    row[columns(tab).index(field)] = value


def add_copy(target: dict, donor: dict, name: str) -> dict:
    copied = copy.deepcopy(table(donor, name))
    existing = [x for x in target["model"]["tables"] if x["name"] == name]
    if existing:
        if len(existing) != 1 or columns(existing[0]) != columns(copied) or rows(target, name):
            raise ValueError(f"target already has populated or incompatible {name}")
        existing[0]["instances"][0]["rows"] = copied["instances"][0]["rows"]
        return existing[0]
    target["model"]["tables"].append(copied)
    return copied


def build(arm: str) -> dict:
    donors = {}
    for name, (relative, digest) in SOURCES.items():
        path = ROOT / relative
        if sha(path) != digest:
            raise ValueError(f"accepted {name} source changed")
        donors[name] = json.loads(path.read_text(encoding="utf-8"))
    if arm not in ("deterministic", "risk"):
        raise ValueError(arm)
    doc = copy.deepcopy(donors["D05"])
    rows(doc, "ProblemDescription")[0][0] = "F02 integrated two-aircraft nested support, paired failure exposure"
    control = table(doc, "Control")
    set_field(control, rows(doc, "Control")[0], "SIMPE", 54.0)
    set_field(control, rows(doc, "Control")[0], "RCEND", 54.0)
    for row in rows(doc, "ResultCollection"):
        set_field(table(doc, "ResultCollection"), row, "RCEND", 54.0)

    # F01 traditional aircraft/LRU/SRU physical chain, with D05's 1M fault rate.
    set_field(table(doc, "System"), rows(doc, "System")[0], "FRT", 1000000.0)
    item = add_copy(doc, donors["F01"], "Item")
    for row in rows(doc, "Item"):
        set_field(item, row, "FRT", 1000000.0)
    add_copy(doc, donors["F01"], "ItemStructure")
    for name in ("ItemRepair", "ItemReplacement"):
        add_copy(doc, donors["F01"], name)
    system_repair = table(doc, "SystemRepair")
    system_repair["instances"][0]["rows"] = copy.deepcopy(rows(donors["F01"], "SystemRepair"))

    # E04 two-hour FAST replenishment supplies the first aircraft LRU demands;
    # removed LRUs use F01's local SRU replacement and local stock return.
    rows(doc, "Station").append(copy.deepcopy(rows(donors["E04"], "Station")[1]))
    add_copy(doc, donors["E04"], "StationStructure")
    stock = add_copy(doc, donors["F01"], "StockAllocation")
    stockrows = rows(doc, "StockAllocation")
    set_field(stock, stockrows[0], "STSIZ", 0)
    set_field(stock, stockrows[1], "STSIZ", 2)
    depot_lru = copy.deepcopy(rows(donors["E04"], "StockAllocation")[1])
    set_field(stock, depot_lru, "STSIZ", 2)
    stockrows.append(depot_lru)

    # A04 repeats two waves across two days; B04's starts put the first
    # turnround across midnight. Both waves require two-aircraft formation.
    profile = table(doc, "OperationProfile")
    profile["instances"][0]["rows"] = copy.deepcopy(rows(donors["A04"], "OperationProfile"))
    profile_rows = rows(doc, "OperationProfile")
    set_field(profile, profile_rows[1], "STIM", 21.5)
    set_field(profile, profile_rows[1], "SPRID", "RISK-MISSION")
    set_field(profile, profile_rows[1], "DTIM", 2.0)
    set_field(profile, profile_rows[2], "STIM", 24.75)
    set_field(profile, profile_rows[2], "DTIM", 2.0)
    mission = table(doc, "MissionType")
    for row in rows(doc, "MissionType"):
        set_field(mission, row, "NOS", 2)
        set_field(mission, row, "MNOS", 2)
        set_field(mission, row, "DURN", 2.0)
        if row[0] == "RISK-MISSION":
            set_field(mission, row, "DESCR", "Two-hour formation with paired failure exposure")
        set_field(mission, row, "MFF", 0.0 if row[0] == "BASIC-MISSION" or arm == "deterministic" else 1.0)
    turnround = add_copy(doc, donors["B04"], "MissionTurnround")
    rows(doc, "MissionTurnround").append(copy.deepcopy(rows(doc, "MissionTurnround")[0]))
    set_field(turnround, rows(doc, "MissionTurnround")[1], "MTID", "RISK-MISSION")

    # C03 shared preparation crew plus D05's shared maintenance worker/PM.
    prep = add_copy(doc, donors["C03"], "MissionPreparation")
    rows(doc, "MissionPreparation").append(copy.deepcopy(rows(doc, "MissionPreparation")[0]))
    set_field(prep, rows(doc, "MissionPreparation")[1], "MTID", "RISK-MISSION")
    rows(doc, "Resource").append(copy.deepcopy(rows(donors["C03"], "Resource")[0]))
    rows(doc, "ResourceAllocation").append(copy.deepcopy(rows(donors["C03"], "ResourceAllocation")[0]))
    tasks = table(doc, "Tasks")
    rows(doc, "Tasks")[:] = [r for r in rows(doc, "Tasks") if r[0] != "CM-DIRECT"]
    rows(doc, "Tasks").append(copy.deepcopy(rows(donors["F01"], "Tasks")[0]))
    rows(doc, "Tasks").append(copy.deepcopy(rows(donors["C03"], "Tasks")[0]))
    set_field(tasks, rows(doc, "Tasks")[-1], "DESCR", "Half-hour shared-crew formation preparation")
    breakdown = table(doc, "TaskBreakDown")
    breakdown["instances"][0]["rows"] = [r for r in rows(doc, "TaskBreakDown") if r[0] != "CM-DIRECT"]
    rows(doc, "TaskBreakDown").extend(copy.deepcopy(rows(donors["F01"], "TaskBreakDown")))
    rows(doc, "TaskBreakDown").extend(copy.deepcopy(rows(donors["C03"], "TaskBreakDown")))
    subresource = table(doc, "SubTaskResource")
    subresource["instances"][0]["rows"] = [r for r in rows(doc, "SubTaskResource") if r[0] != "CM-DIRECT"]
    prep_resource = copy.deepcopy(rows(donors["C03"], "SubTaskResource")[0])
    rows(doc, "SubTaskResource").append(prep_resource)
    for seq in (1, 2):
        row = copy.deepcopy(rows(donors["D05"], "SubTaskResource")[1])
        set_field(subresource, row, "TID", "E01-SURP")
        set_field(subresource, row, "SEQ", seq)
        rows(doc, "SubTaskResource").append(row)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for arm in ("deterministic", "risk"):
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(build(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        print(json.dumps({"arm": arm, "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
