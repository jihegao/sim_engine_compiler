"""Derive a two-mission preventive-maintenance counter from accepted D04."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D04-flight-hour-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table")
    return found[0]


def fields(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def put(t: dict, row: list, **changes: object) -> None:
    names = fields(t)
    for name, value in changes.items():
        row[names.index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted D04 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    put(table(doc, "ProblemDescription"), rows(table(doc, "ProblemDescription"))[0],
        PDESC="D10 two-mission PM, five fixed waves")
    mission = table(doc, "MissionType")
    if len(rows(mission)) != 2:
        raise ValueError("expected D04's two mission types")
    put(mission, rows(mission)[0], DESCR="Four-hour generic mission", DURN=4.0)
    profile = table(doc, "OperationProfile")
    if [r[fields(profile).index("STIM")] for r in rows(profile)] != [8.0, 40.0]:
        raise ValueError("unexpected D04 wave schedule")
    first, short = rows(profile)
    waves = [copy.deepcopy(first)]
    for when in (16.0, 20.0, 48.0, 52.0):
        wave = copy.deepcopy(short)
        put(profile, wave, STIM=when)
        waves.append(wave)
    profile["instances"][0]["rows"] = waves
    pm = table(doc, "MaterielPM")
    put(pm, rows(pm)[0], PMID="MS2", DESCR="Every two completed missions",
        PMINT=2.0, OPID="MISSIONS")
    loc = table(doc, "PMLocation")
    put(loc, rows(loc)[0], PMID="MS2", TID="PM-MS2")
    task = table(doc, "Tasks")
    put(task, rows(task)[0], TID="PM-MS2", DESCR="One-hour two-mission service")
    breakdown = table(doc, "TaskBreakDown")
    put(breakdown, rows(breakdown)[0], TID="PM-MS2")
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
        raise ValueError("frozen D10 mission-count input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
