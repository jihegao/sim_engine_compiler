"""Derive a long-delayed calendar PM with ENREG=N from accepted D03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return found[0]


def put(t: dict, **changes: object) -> None:
    names = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"one {t['name']} row required")
    for name, value in changes.items():
        rows[0][names.index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted D03 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    put(table(doc, "ProblemDescription"), PDESC="D11 long-delayed calendar PM, ENREG N")
    rows = table(doc, "OperationProfile")["instances"][0]["rows"]
    if len(rows) != 3 or [r[2] for r in rows] != [8, 20, 32]:
        raise ValueError("accepted D03 mission schedule differs")
    rows[-1][2] = 23.5
    rows[-1][1] = "LONG-MISSION"
    mission = table(doc, "MissionType")
    columns = [c["name"] for c in mission["columns"]]
    mission_rows = mission["instances"][0]["rows"]
    if len(mission_rows) != 1 or mission_rows[0][columns.index("DURN")] != 2:
        raise ValueError("accepted D03 mission type differs")
    long_row = copy.deepcopy(mission_rows[0])
    long_row[columns.index("MTID")] = "LONG-MISSION"
    long_row[columns.index("DESCR")] = "Twenty-six-hour calendar PM delay mission"
    long_row[columns.index("DURN")] = 26.0
    mission_rows.append(long_row)
    put(table(doc, "Control"), SIMPE=84.0, RCEND=84.0)
    collection = table(doc, "ResultCollection")
    rc_names = [c["name"] for c in collection["columns"]]
    rc_rows = collection["instances"][0]["rows"]
    if len(rc_rows) != 2 or {r[rc_names.index("RTYPE")] for r in rc_rows} != {"MISSION", "SYSTEM"}:
        raise ValueError("accepted D03 result collection differs")
    for row in rc_rows:
        row[rc_names.index("RCEND")] = 84.0
    put(table(doc, "MaterielPM"), ENREG="N")
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
        raise ValueError("frozen long-drift input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
