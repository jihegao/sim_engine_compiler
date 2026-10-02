"""Build NBREQ1 and NBREQ3 around accepted G08 A-root NBREQ2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G08-tree-root-panel-v1.0.0" / "roota-input.json"
PARENT_SHA = "4920a7bc2ae01126ae27fdc97fde1d7f2c7d051545315b154f5491890969dd26"
ARMS = {"low": 1, "high": 3}


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
        raise ValueError("accepted G08 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    if rows(doc, "RBDTree") != [["G08-TREE", "Three leaf paths through common root POS-A", 2, None]]:
        raise ValueError("parent tree changed")
    if [r[1:3] for r in rows(doc, "RBDTreeStructure")] != [["POS-A", x] for x in ("POS-B", "POS-C", "POS-D")]:
        raise ValueError("parent edges changed")
    rows(doc, "ProblemDescription")[0][0] = f"G08.var03 A-root three-leaf tree NBREQ{ARMS[arm]} boundary"
    rows(doc, "RBDTree")[0][2] = ARMS[arm]
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode()
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(result))


if __name__ == "__main__":
    main()
