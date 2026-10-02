"""Align physical and tree multiplicity of healthy POS-C against NBREQ3 control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G08-var03-nbreq-boundary-v1.0.0" / "high-input.json"
PARENT_SHA = "644ddfbc8743abd9f76866bb3b558776dbda295e6fd27fde43b178daa1a62051"


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(name)
    return matches[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted NBREQ3 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    tree = rows(doc, "RBDTree")
    if tree != [["G08-TREE", "Three leaf paths through common root POS-A", 3, None]]:
        raise ValueError("parent threshold changed")
    structure = rows(doc, "RBDTreeStructure")
    if [r[1:6] for r in structure] != [["POS-A", x, "G04-OPS", "G04-OPS", 1] for x in ("POS-B", "POS-C", "POS-D")]:
        raise ValueError("parent tree links changed")
    physical = rows(doc, "MaterielStructure")
    c = [r for r in physical if r[0:2] == ["POS-C", "TEACH-AIR-01"]]
    if len(c) != 1 or c[0][2] != 1:
        raise ValueError("parent physical C changed")
    if any(r[2] == "POS-C" for r in rows(doc, "FailureMode")):
        raise ValueError("C must have no failure mode")
    rows(doc, "ProblemDescription")[0][0] = "G08.var04 two healthy POS-C descendants, four leaf paths NBREQ3"
    c[0][2] = 2
    structure[1][5] = 2
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "repeated-input.json"
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
