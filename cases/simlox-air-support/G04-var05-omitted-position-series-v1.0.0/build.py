"""Build paired omitted-versus-included POS-D active RBD models."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "one-input.json"
PARENT_SHA = "cfdf287c4de93638e8117c71ad3de1846da3c62c24254bf7d2a3f0f7c7c0c4d7"
ARMS = ("omitted", "included")


def table(doc: dict, name: str) -> dict:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent input changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "RBDParallel") != [["G04-PARALLEL", "Active 1-of-3 fixed-mission threshold", 1, 3, 0.0, "N", None]]:
        raise ValueError("parent RBD changed")
    if [r[0] for r in rows(doc, "FailureMode")] != ["FM-POS-A", "FM-POS-B"]:
        raise ValueError("parent failure modes changed")
    if [r[0] for r in rows(doc, "MaterielPosition")] != ["POS-A", "POS-B", "POS-C"]:
        raise ValueError("parent positions changed")
    rows(doc, "ProblemDescription")[0][0] = f"G04.var05 failing POS-D {arm} from active 1-of-3 RBD"
    rows(doc, "MaterielPosition").append(["POS-D", "Fourth failing LRU position", None])
    structure = rows(doc, "MaterielStructure")
    if [r[0] for r in structure] != ["POS-A", "POS-B", "POS-C", "TEACH-LRU-01", "TEACH-LRU-01", "TEACH-LRU-01"]:
        raise ValueError("parent physical structure changed")
    structure.insert(3, ["POS-D", "TEACH-AIR-01", 1, 1.0, None, None])
    structure.append(["TEACH-LRU-01", "POS-D", 1, 1.0, None, None])
    rows(doc, "FailureMode").append(["FM-POS-D", "Position D direct repair", "POS-D", 1000000.0, "OPHOURS", 1.0, None, None, None])
    rows(doc, "CMLocation").append(["FM-POS-D", "TEACH-AIR-01", "BASE-01", 0.5, None, None, 1.0, None, None, None])
    rows(doc, "MaterielOperationalModes").append(["POS-D", "G04-OPS", None, None, 1.0, None])
    if arm == "included":
        rbd = rows(doc, "RBDParallel")[0]
        rbd[1] = "Active 1-of-4 including failing POS-D"
        rbd[3] = 4
        rows(doc, "RBDParallelStructure").append(["G04-PARALLEL", "POS-D", "G04-OPS", 1, 1, None])
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} input differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
