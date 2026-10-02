"""Add independent healthy E-to-F root-to-leaf path to accepted G08 NBREQ1 tree."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G08-var03-nbreq-boundary-v1.0.0" / "low-input.json"
PARENT_SHA = "ae94fbf97c6ce6a9382fb97cab0bf63d822c769a395babf6f3f6d55cb4b9a343"


def table(doc: dict, name: str) -> dict:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G08 single-root parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "RBDTree") != [["G08-TREE", "Three leaf paths through common root POS-A", 1, None]]:
        raise ValueError("accepted NBREQ1 tree changed")
    if [r[1:3] for r in rows(doc, "RBDTreeStructure")] != [["POS-A", x] for x in ("POS-B", "POS-C", "POS-D")]:
        raise ValueError("accepted A-root edges changed")
    physical, modes = rows(doc, "MaterielStructure"), rows(doc, "MaterielOperationalModes")
    if [r[0] for r in physical[:4]] != [f"POS-{x}" for x in "ABCD"] or len(physical) != 8:
        raise ValueError("accepted physical positions changed")
    if [r[0] for r in modes] != ["TEACH-AIR-01"] + [f"POS-{x}" for x in "ABCD"]:
        raise ValueError("accepted modes changed")
    if [r[2] for r in rows(doc, "FailureMode")] != ["POS-A", "POS-B"]:
        raise ValueError("accepted failures changed")
    rows(doc, "ProblemDescription")[0][0] = "G08.var01 two independent roots A and E, NBREQ1"
    positions = rows(doc, "MaterielPosition")
    positions.extend([["POS-E", "Independent healthy tree root", None],
                      ["POS-F", "Healthy leaf of independent root", None]])
    physical[4:4] = [["POS-E", "TEACH-AIR-01", 1, 1.0, None, None],
                     ["POS-F", "TEACH-AIR-01", 1, 1.0, None, None]]
    physical.extend([["TEACH-LRU-01", "POS-E", 1, 1.0, None, None],
                     ["TEACH-LRU-01", "POS-F", 1, 1.0, None, None]])
    modes.extend([["POS-E", "G04-OPS", None, None, 1.0, None],
                  ["POS-F", "G04-OPS", None, None, 1.0, None]])
    rows(doc, "RBDTreeStructure").append(["G08-TREE", "POS-E", "POS-F", "G04-OPS", "G04-OPS", 1, None])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "multiroot-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen candidate differs")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
