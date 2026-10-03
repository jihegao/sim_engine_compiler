"""Nest a passive B/E parallel fallback in the first G08 tree leaf."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G08-var03-nbreq-boundary-v1.0.0" / "high-input.json"
PARENT_SHA = "644ddfbc8743abd9f76866bb3b558776dbda295e6fd27fde43b178daa1a62051"
SCHEMA_DONOR = HERE.parent / "G04-series-active-parallel-v1.0.0" / "parallel-input.json"
SCHEMA_DONOR_SHA = "c9ec1d90f9e1ae6e6c972218fb406abd1b9ce4a76c7e34310372ebedac665e3e"
ARMS = {"instant": 0.0, "delay05": 0.5}
RBID = "G08-BE-PASSIVE"


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
        raise ValueError("accepted G08 NBREQ3 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    tree = rows(doc, "RBDTreeStructure")
    if tree != [["G08-TREE", "POS-A", x, "G04-OPS", "G04-OPS", 1, None] for x in ("POS-B", "POS-C", "POS-D")]:
        raise ValueError("accepted tree links changed")
    if rows(doc, "RBDTree")[0][2] != 3 or any(t["name"] in ("RBDParallel", "RBDParallelStructure") for t in doc["model"]["tables"]):
        raise ValueError("accepted RBD shape changed")
    donor_raw = SCHEMA_DONOR.read_bytes()
    if hashlib.sha256(donor_raw).hexdigest() != SCHEMA_DONOR_SHA:
        raise ValueError("accepted parallel schema donor changed")
    donor_tables = {t["name"]: t for t in json.loads(donor_raw)["model"]["tables"]}
    insert_at = next(i for i, t in enumerate(doc["model"]["tables"]) if t["name"] == "RBDTree")
    for name in ("RBDParallel", "RBDParallelStructure"):
        template = copy.deepcopy(donor_tables[name])
        template["instances"][0]["rows"] = []
        doc["model"]["tables"].insert(insert_at, template)
        insert_at += 1
    if [r[0] for r in rows(doc, "MaterielPosition")] != ["POS-A", "POS-B", "POS-C", "POS-D"]:
        raise ValueError("accepted positions changed")
    structure = rows(doc, "MaterielStructure")
    if len(structure) != 8 or structure[3] != ["POS-D", "TEACH-AIR-01", 1, 1.0, None, None]:
        raise ValueError("accepted physical structure changed")
    modes = rows(doc, "MaterielOperationalModes")
    if [r[0] for r in modes] != ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C", "POS-D"]:
        raise ValueError("accepted operational modes changed")
    rows(doc, "ProblemDescription")[0][0] = f"G08.var06 nested B/E passive leaf; switch {ARMS[arm]:g} h"
    rows(doc, "MaterielPosition").append(["POS-E", "Healthy passive nested fallback position", None])
    structure.insert(4, ["POS-E", "TEACH-AIR-01", 1, 1.0, None, None])
    structure.append(["TEACH-LRU-01", "POS-E", 1, 1.0, None, None])
    modes.append(["POS-E", "G04-OPS", None, None, 1.0, None])
    rows(doc, "RBDParallel").append([RBID, "B active and E passive within tree leaf", 1, 1, ARMS[arm], "N", None])
    rows(doc, "RBDParallelStructure").extend([
        [RBID, "POS-B", "G04-OPS", 1, 1, None],
        [RBID, "POS-E", "G04-OPS", 1, 2, None],
    ])
    tree[0][2] = RBID
    tree[0][4] = None  # Nested RBD has no direct tree-edge operational mode.
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    found = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} differs")
        found[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(found))


if __name__ == "__main__":
    main()
