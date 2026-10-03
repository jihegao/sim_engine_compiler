"""Append a short two-aircraft mission to the accepted F02 active-removal input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var04-terminal-repair-v1.0.0"
PARENT_INPUT = PARENT / "repair-input.json"
PARENT_SHA = "7605c2a22396cc9d7962c96ede757b93b11c94e01480ed625fdfd63f359297ce"
OUTPUT = HERE / "preassignment-input.json"
NEW_MTID = "TERMINAL-HOLD"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_for(table: dict, field: str, value: object) -> list:
    columns = [c["name"] for c in table["columns"]]
    matches = [r for inst in table["instances"] for r in inst["rows"] if r[columns.index(field)] == value]
    if len(matches) != 1 or len(table["instances"]) != 1:
        raise ValueError(f"expected one {table['name']} {field}={value}")
    return copy.deepcopy(matches[0])


def set_field(table: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in table["columns"]].index(field)] = value


def build() -> dict:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted active-removal parent changed")
    doc = copy.deepcopy(json.loads(PARENT_INPUT.read_bytes()))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    control = tables["Control"]
    cr = control["instances"][0]["rows"]
    cf = [c["name"] for c in control["columns"]]
    if len(cr) != 1 or cr[0][cf.index("SIMPE")] != 60 or cr[0][cf.index("RCEND")] != 60:
        raise ValueError("unexpected 60-hour cutoff")
    cr[0][cf.index("SIMPE")] = 65.0

    mission = tables["MissionType"]
    mr = row_for(mission, "MTID", "BASIC-MISSION")
    assert mr[[c["name"] for c in mission["columns"]].index("DURN")] == 2
    set_field(mission, mr, "MTID", NEW_MTID)
    set_field(mission, mr, "DESCR", "Short terminal formation held by unavailable aircraft")
    set_field(mission, mr, "DURN", 0.25)
    mission["instances"][0]["rows"].append(mr)

    profile = tables["OperationProfile"]
    pr = row_for(profile, "SPRID", "BASIC-MISSION")
    assert pr[[c["name"] for c in profile["columns"]].index("PRID")] == "A09-DAILY-TWO-WAVE"
    set_field(profile, pr, "PRID", "BASIC-SCHEDULE")
    set_field(profile, pr, "SPRID", NEW_MTID)
    set_field(profile, pr, "STIM", 60.5)
    profile["instances"][0]["rows"].append(pr)

    for name in ("MissionPreparation", "MissionTurnround"):
        table = tables[name]
        row = row_for(table, "MTID", "BASIC-MISSION")
        set_field(table, row, "MTID", NEW_MTID)
        table["instances"][0]["rows"].append(row)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen preassignment input changed")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
