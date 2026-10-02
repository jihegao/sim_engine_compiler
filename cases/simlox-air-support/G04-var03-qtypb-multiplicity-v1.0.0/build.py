"""Build a second zero-rate POS-C copy in the accepted active 2-of-3 RBD."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G04-three-branch-threshold-v1.0.0" / "two-input.json"
PARENT_SHA = "38f85af4c121668eee3d31b07bb435b74571c5be6d63ddccff034549609ec319"


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
        raise ValueError("accepted parent input changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "RBDParallel") != [["G04-PARALLEL", "Active 2-of-3 fixed-mission threshold", 2, 3, 0.0, "N", None]]:
        raise ValueError("parent RBD changed")
    if rows(doc, "RBDParallelStructure") != [["G04-PARALLEL", "POS-A", "G04-OPS", 1, 1, None],
                                               ["G04-PARALLEL", "POS-B", "G04-OPS", 1, 1, None],
                                               ["G04-PARALLEL", "POS-C", "G04-OPS", 1, 1, None]]:
        raise ValueError("parent RBD structure changed")
    structure = rows(doc, "MaterielStructure")
    if structure[2] != ["POS-C", "TEACH-AIR-01", 1, 1.0, None, None]:
        raise ValueError("parent physical POS-C changed")
    if [r[0] for r in rows(doc, "FailureMode")] != ["FM-POS-A", "FM-POS-B"]:
        raise ValueError("parent failure modes changed")
    rows(doc, "ProblemDescription")[0][0] = "G04.var03 active 2-of-4 with two POS-C copies and QTYPB 2"
    structure[2][2] = 2
    rbd = rows(doc, "RBDParallel")[0]
    rbd[1] = "Active 2-of-4 with two zero-failure POS-C copies"
    rbd[3] = 4
    rows(doc, "RBDParallelStructure")[2][3] = 2
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "native-input.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
