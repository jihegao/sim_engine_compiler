"""Isolate NC-set POS-B usage zero versus one in BASIC missions."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G09-var03-default-noncritical-v1.0.1" / "omitted-nc-b1-input.json"
PARENT_SHA = "40210448fc3ccabc93c681272bf179026342202ba2ae36cfd8302769523a3e11"
ARMS = {"ncuse0": 0.0, "ncuse1": 1.0}


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G09.var03 NC parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "RBDNonCriticalSetItems") != [["G09-NC-B", "POS-B", 1, 1.0, None]]:
        raise ValueError("parent NC set item changed")
    if rows(doc, "MaterielOperationalModes")[-1] != ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", "G09-NC-B", 1.0, None]:
        raise ValueError("parent BASIC NC selector changed")
    if rows(doc, "RBDSeriesStructure") != [["G09-SER-RBD", "POS-A", "G04-OPS", 1, None]]:
        raise ValueError("parent BASIC series changed")
    if rows(doc, "MissionOperationalModes") != [
        ["BASIC-MISSION", "TEACH-AIR-01", "G09-SER-OPS", None],
        ["PAR-MISSION", "TEACH-AIR-01", "G04-OPS", None],
    ]:
        raise ValueError("parent mission mapping changed")
    failure = rows(doc, "FailureMode")
    if [r[3] for r in failure] != [300000.0, 600000.0]:
        raise ValueError("parent failure rates changed")
    if [(r[1], r[2]) for r in rows(doc, "OperationProfile")] != [
        ("BASIC-MISSION", 8.0), ("PAR-MISSION", 20.0), ("BASIC-MISSION", 32.0)
    ]:
        raise ValueError("parent schedule changed")
    failure[0][3] = 1e-9  # common positive A rate removes competing A failure
    rows(doc, "ProblemDescription")[0][0] = f"G09.var06 BASIC NC-set POS-B USERT={ARMS[arm]:g}"
    rows(doc, "RBDNonCriticalSetItems")[0][3] = ARMS[arm]
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    hashes = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input changed")
        hashes[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(hashes))


if __name__ == "__main__":
    main()
