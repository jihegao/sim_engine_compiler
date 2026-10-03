"""Assign series and parallel RBDs to two mission types of one aircraft."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-series-active-parallel-v1.0.1" / "parallel-input.json"
PARENT_SHA = "ea56a9daf8705189c9162529355b28636ef7db168987b17ee90cdedbe9bb4b6f"
SCHEMA_DONOR = HERE.parent / "G04-series-active-parallel-v1.0.1" / "series-input.json"
SCHEMA_DONOR_SHA = "3adc1cf0d75dd9418e816d0e06bdc502af5d37d975beafbba8f781c94d2763e8"
MODE = "G09-SER-OPS"
SERIES = "G09-SER-RBD"
PAR_MISSION = "PAR-MISSION"


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G04 parallel parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if any(t["name"] in ("RBDSeries", "RBDSeriesStructure") for t in doc["model"]["tables"]):
        raise ValueError("accepted parent unexpectedly contains series tables")
    if [r[2] for r in rows(doc, "OperationProfile")] != [8.0, 20.0, 32.0]:
        raise ValueError("accepted mission times changed")
    if [r[0] for r in rows(doc, "MissionType")] != ["BASIC-MISSION"]:
        raise ValueError("accepted mission type changed")
    if rows(doc, "MissionOperationalModes") != [["BASIC-MISSION", "TEACH-AIR-01", "G04-OPS", None]]:
        raise ValueError("accepted mission mode changed")
    if rows(doc, "MaterielOperationalModes")[0] != ["TEACH-AIR-01", "G04-OPS", "G04-PARALLEL", None, 1.0, None]:
        raise ValueError("accepted system RBD mode changed")
    donor_raw = SCHEMA_DONOR.read_bytes()
    if hashlib.sha256(donor_raw).hexdigest() != SCHEMA_DONOR_SHA:
        raise ValueError("accepted series schema donor changed")
    donor_tables = {t["name"]: t for t in json.loads(donor_raw)["model"]["tables"]}
    insert_at = next(i for i, t in enumerate(doc["model"]["tables"]) if t["name"] == "RBDParallel")
    for name in ("RBDSeries", "RBDSeriesStructure"):
        template = copy.deepcopy(donor_tables[name])
        template["instances"][0]["rows"] = []
        doc["model"]["tables"].insert(insert_at, template)
        insert_at += 1

    rows(doc, "ProblemDescription")[0][0] = "G09.var01 one aircraft: series, parallel, series missions"
    missions = rows(doc, "MissionType")
    missions[0][1] = "Two-hour series-mode mission"
    parallel = copy.deepcopy(missions[0])
    parallel[0], parallel[1] = PAR_MISSION, "Two-hour parallel-mode mission"
    missions.append(parallel)
    rows(doc, "OperationProfile")[1][1] = PAR_MISSION
    rows(doc, "OperationalModes").append([MODE, "Series RBD for BASIC-MISSION", None])
    mission_modes = rows(doc, "MissionOperationalModes")
    mission_modes[0][2] = MODE
    mission_modes.append([PAR_MISSION, "TEACH-AIR-01", "G04-OPS", None])
    rows(doc, "MaterielOperationalModes").append(["TEACH-AIR-01", MODE, SERIES, None, 1.0, None])
    rows(doc, "RBDSeries").append([SERIES, "Both physical positions required", None])
    rows(doc, "RBDSeriesStructure").extend([
        [SERIES, "POS-A", "G04-OPS", 1, None],
        [SERIES, "POS-B", "G04-OPS", 1, None],
    ])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "mixed-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen mixed input differs")
    print(json.dumps({"mixed_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
