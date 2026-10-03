"""Factor selected BASIC system and POS-B usage against accepted direct rates."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_PACKAGE = HERE.parent / "G09-var04-usert-boundary-v1.0.1"
PARENT = PARENT_PACKAGE / "use1-input.json"
PARENT_SHA = "957e7b16a75c2cc06a6bf2ef6a2a7b9ae0a44e683349c248383281b3ffec5c85"
DIRECT_HALF = PARENT_PACKAGE / "use05-input.json"
DIRECT_HALF_SHA = "4e121c8b8c86bb650e7060ad77e66049d8eaedc89728a4cc18a7c486b1d27c81"
ARMS = {"factorhalf": 1.0, "factorfull": 2.0}


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
        raise ValueError("accepted full-rate parent changed")
    if hashlib.sha256(DIRECT_HALF.read_bytes()).hexdigest() != DIRECT_HALF_SHA:
        raise ValueError("accepted direct half-rate control changed")
    doc = copy.deepcopy(json.loads(raw))
    modes = rows(doc, "MaterielOperationalModes")
    if modes[3] != ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", None, 1.0, None]:
        raise ValueError("parent BASIC system mode changed")
    if modes[-1] != ["POS-B", "G09-B-USE", None, None, 1.0, None]:
        raise ValueError("parent BASIC B leaf mode changed")
    if modes[0] != ["TEACH-AIR-01", "G04-OPS", "G04-PARALLEL", None, 1.0, None] or \
       modes[2] != ["POS-B", "G04-OPS", None, None, 1.0, None]:
        raise ValueError("parent PAR system or B mode changed")
    if rows(doc, "RBDSeriesStructure")[-1] != ["G09-SER-RBD", "POS-B", "G09-B-USE", 1, None]:
        raise ValueError("parent B leaf selector changed")
    if [(r[1], r[2]) for r in rows(doc, "OperationProfile")] != [
        ("BASIC-MISSION", 8.0), ("PAR-MISSION", 20.0), ("BASIC-MISSION", 32.0)
    ]:
        raise ValueError("parent schedule changed")
    rows(doc, "ProblemDescription")[0][0] = (
        f"G09.var05 BASIC system USERT0.5 x B USERT{ARMS[arm]:g}"
    )
    modes[3][4] = 0.5
    modes[-1][4] = ARMS[arm]
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
