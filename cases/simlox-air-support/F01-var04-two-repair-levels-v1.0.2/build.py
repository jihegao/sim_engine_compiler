"""Derive an SRU level-2 depot repair from the accepted F01 three-level chain."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "F01-var01-two-three-level-v1.0.1/three-level-input.json"
DONOR = ROOT / "I01-var03-level-filter-v1.0.0/basic-base-input.json"
PARENT_SHA = "ae0181581822422aaf3c8bc5b7c0352c8bf31187178408e4f211102e438c77b5"
DONOR_SHA = "483a99ec2c4512f2b02c7f67f08e76b7ac218470ba64b0ecadc91c1db4a9daae"
OUTPUT = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table and instance required")
    return found[0]


def names(t: dict) -> list[str]:
    return [c["name"] for c in t["columns"]]


def rows(t: dict) -> list[list]:
    return t["instances"][0]["rows"]


def add(t: dict, **values: object) -> None:
    cols = names(t)
    if set(values) - set(cols):
        raise ValueError(f"unknown {t['name']} field")
    rows(t).append([values.get(name) for name in cols])


def donor_row(donor: dict, name: str, predicate) -> list:
    t = table(donor, name)
    matches = [r for r in rows(t) if predicate(dict(zip(names(t), r)))]
    if len(matches) != 1:
        raise ValueError(f"unexpected donor {name} rows")
    return copy.deepcopy(matches[0])


def build() -> dict:
    if sha(PARENT) != PARENT_SHA or sha(DONOR) != DONOR_SHA:
        raise ValueError("accepted parent or allocation reference changed")
    doc = copy.deepcopy(json.loads(PARENT.read_text(encoding="utf-8")))
    donor = json.loads(DONOR.read_text(encoding="utf-8"))
    for name in ("TaskCategory", "TaskLevel", "MaintenanceAllocation"):
        extra = copy.deepcopy(table(donor, name))
        extra["instances"][0]["rows"] = []
        doc["model"]["tables"].append(extra)
    desc = table(doc, "ProblemDescription")
    rows(desc)[0][names(desc).index("PDESC")] = (
        "F01.var04 nested LRU/SRU: local replacement, level-2 depot repair, 42h closure"
    )
    control = table(doc, "Control")
    rows(control)[0][names(control).index("SIMPE")] = 42.0
    rows(control)[0][names(control).index("RCEND")] = 42.0
    collection = table(doc, "ResultCollection")
    for row in rows(collection):
        row[names(collection).index("RCEND")] = 42.0
    station = table(doc, "Station")
    rows(station).append(donor_row(donor, "Station", lambda r: r["STID"] == "DEPOT-01"))
    structure = table(doc, "StationStructure")
    rows(structure).append(donor_row(donor, "StationStructure", lambda r: r["STID"] == "BASE-01" and r["MSTID"] == "DEPOT-01"))

    repair = table(doc, "ItemRepair")
    col = names(repair)
    sru = [r for r in rows(repair) if r[col.index("IID")] == "TEACH-SRU-01"]
    if len(sru) != 1 or sru[0][col.index("STID")] != "BASE-01" or sru[0][col.index("DIRPT")] != 1.0:
        raise ValueError("unexpected parent SRU repair")
    sru[0][col.index("DIRPTID")] = "F01-SRU-DIRP"
    remote = copy.deepcopy(sru[0])
    remote[col.index("STID")] = "DEPOT-01"
    rows(repair).append(remote)

    add(table(doc, "Tasks"), TID="F01-SRU-DIRP", DESCR="Level-2 failed SRU direct repair", TCID="SRU-CM", TLID="DEPOT")
    add(table(doc, "TaskCategory"), TCID="SRU-CM", DESCR="SRU corrective maintenance")
    add(table(doc, "TaskLevel"), TLID="BASE", LEVL=1)
    add(table(doc, "TaskLevel"), TLID="DEPOT", LEVL=2)
    add(table(doc, "MaintenanceAllocation"), POINT="AIR_BASIC", TCID="SRU-CM", TLID="DEPOT", STID="DEPOT-01")
    add(table(doc, "StockAllocation"), POINT="AIR_BASIC", IID="TEACH-SRU-01", STID="DEPOT-01", STSIZ=0)
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
    print(json.dumps({"parent_sha256": PARENT_SHA, "reference_sha256": DONOR_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
