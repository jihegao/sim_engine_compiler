"""Isolate four BASIC POS-B usage rates with negligible POS-A ordinary failure."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G09-var01-mission-rbd-v1.0.0" / "mixed-input.json"
PARENT_SHA = "62e48b3eae86e0713e0a5c641ec28dddc3cc3cd81dc99be2659ceeee2f63475b"
ARMS = {"use0": 0.0, "use05": 0.5, "use1": 1.0, "use2": 2.0}
MODE = "G09-B-USE"


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
        raise ValueError("accepted G09.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "MaterielOperationalModes") != [
        ["TEACH-AIR-01", "G04-OPS", "G04-PARALLEL", None, 1.0, None],
        ["POS-A", "G04-OPS", None, None, 1.0, None],
        ["POS-B", "G04-OPS", None, None, 1.0, None],
        ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", None, 1.0, None],
    ]:
        raise ValueError("parent modes changed")
    if rows(doc, "RBDSeriesStructure") != [
        ["G09-SER-RBD", "POS-A", "G04-OPS", 1, None],
        ["G09-SER-RBD", "POS-B", "G04-OPS", 1, None],
    ]:
        raise ValueError("parent BASIC series changed")
    if rows(doc, "RBDParallelStructure") != [
        ["G04-PARALLEL", "POS-A", "G04-OPS", 1, 1, None],
        ["G04-PARALLEL", "POS-B", "G04-OPS", 1, 1, None],
    ]:
        raise ValueError("parent PAR controls changed")
    if [(r[1], r[2]) for r in rows(doc, "OperationProfile")] != [
        ("BASIC-MISSION", 8.0), ("PAR-MISSION", 20.0), ("BASIC-MISSION", 32.0)
    ]:
        raise ValueError("parent mission schedule changed")
    failure = rows(doc, "FailureMode")
    if [r[3] for r in failure] != [300000.0, 600000.0]:
        raise ValueError("parent physical rates changed")
    failure[0][3] = 1e-9  # common controlled A suppression; B rate remains accepted
    rows(doc, "ProblemDescription")[0][0] = f"G09.var04 isolated B BASIC USERT={ARMS[arm]:g}; PAR B stays 1"
    rows(doc, "OperationalModes").append([MODE, "BASIC series POS-B relative usage", None])
    rows(doc, "MaterielOperationalModes").append(["POS-B", MODE, None, None, ARMS[arm], None])
    rows(doc, "RBDSeriesStructure")[1][2] = MODE
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
