"""Derive a bounded three-operation-hour PM threshold from accepted D03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
PARENT_SHA256 = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
OUTPUT = HERE / "native-input.json"


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return found[0]


def names(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def one(t: dict, **values: object) -> None:
    fields = names(t)
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or set(values) - set(fields):
        raise ValueError(f"unexpected {t['name']} shape")
    for field, value in values.items():
        rows[0][fields.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    one(table(model, "ProblemDescription"), PDESC="D04 one-aircraft OPHOURS PM after 2h and 1h missions")
    mission = table(model, "MissionType")
    fields = names(mission)
    rows = mission["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][fields.index("MTID")] != "BASIC-MISSION":
        raise ValueError("unexpected parent mission")
    short = copy.deepcopy(rows[0])
    short[fields.index("MTID")] = "SHORT-MISSION"
    short[fields.index("DESCR")] = "One-hour generic mission"
    short[fields.index("DURN")] = 1.0
    rows.append(short)
    profile = table(model, "OperationProfile")
    pf = names(profile)
    waves = profile["instances"][0]["rows"]
    if len(waves) != 3 or [x[pf.index("STIM")] for x in waves] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected parent waves")
    second = copy.deepcopy(waves[2])
    second[pf.index("SPRID")] = "SHORT-MISSION"
    second[pf.index("STIM")] = 40.0
    profile["instances"][0]["rows"] = [waves[0], second]
    one(table(model, "MaterielPM"), PMID="OP3", DESCR="Three-operation-hour service",
        PMINT=3.0, OPID="OPHOURS")
    one(table(model, "PMLocation"), PMID="OP3", TID="PM-OP3")
    one(table(model, "Tasks"), TID="PM-OP3", DESCR="One-hour operation-hour service")
    one(table(model, "TaskBreakDown"), TID="PM-OP3")
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
        raise ValueError("frozen D04 input differs from builder")
    print(json.dumps({"case_id": "D04", "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "parent_sha256": PARENT_SHA256, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
