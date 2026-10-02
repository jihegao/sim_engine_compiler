"""Replace the bridge slot with a two-position nested series RBD."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G07-var03-bridge-failure-v1.0.0" / "brfirst-input.json"
PARENT_SHA = "b6c40f551355e63e7dc031311794b5dfe1fbda13164d4cffcfce12c1844e8dfd"
RBID = "G07-BR-SERIES"


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G07.var03 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    bridge = rows(doc, "RBDBridge")
    if len(bridge) != 1 or bridge[0][2:7] != ["POS-E", "POS-A", "POS-B", "POS-C", "POS-D"]:
        raise ValueError("accepted bridge slots changed")
    if rows(doc, "RBDSeries") or rows(doc, "RBDSeriesStructure"):
        raise ValueError("accepted nested series not empty")
    positions = rows(doc, "MaterielPosition")
    if [r[0] for r in positions] != [f"POS-{x}" for x in "ABCDE"]:
        raise ValueError("accepted positions changed")
    structure = rows(doc, "MaterielStructure")
    if len(structure) != 10 or structure[4] != ["POS-E", "TEACH-AIR-01", 1, 1.0, None, None]:
        raise ValueError("accepted structure changed")
    modes = rows(doc, "MaterielOperationalModes")
    if len(modes) != 6 or modes[-1] != ["POS-E", "G04-OPS", None, None, 1.0, None]:
        raise ValueError("accepted materiel modes changed")
    rows(doc, "ProblemDescription")[0][0] = "G07.var05 BR is nested B+F series; direct routes stay available"
    positions.append(["POS-F", "Healthy nested-series LRU position", None])
    structure.insert(5, ["POS-F", "TEACH-AIR-01", 1, 1.0, None, None])
    structure.append(["TEACH-LRU-01", "POS-F", 1, 1.0, None, None])
    modes.append(["POS-F", "G04-OPS", None, None, 1.0, None])
    rows(doc, "RBDSeries").append([RBID, "B and healthy F required in bridge slot", None])
    rows(doc, "RBDSeriesStructure").extend([
        [RBID, "POS-B", "G04-OPS", 1, None],
        [RBID, "POS-F", "G04-OPS", 1, None],
    ])
    bridge[0][1] = "BR contains nested B+F series"
    bridge[0][4] = RBID
    bridge[0][9] = None  # converter #462: nested reliability blocks cannot receive an OPMID
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "nested-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"nested": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
