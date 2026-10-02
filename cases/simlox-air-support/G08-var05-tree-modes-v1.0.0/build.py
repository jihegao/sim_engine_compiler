"""Build separate tree mother-mode and descendant-mode 0.75 usage arms."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G08-tree-root-panel-v1.0.0" / "roota-input.json"
PARENT_SHA = "4920a7bc2ae01126ae27fdc97fde1d7f2c7d051545315b154f5491890969dd26"
ARMS = ("mother75", "sub75")


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
        raise ValueError("accepted root-A tree changed")
    doc = copy.deepcopy(json.loads(raw))
    tree = rows(doc, "RBDTreeStructure")
    if [r[1:6] for r in tree] != [["POS-A", x, "G04-OPS", "G04-OPS", 1] for x in ("POS-B", "POS-C", "POS-D")]:
        raise ValueError("accepted tree modes or links changed")
    base_modes = rows(doc, "MaterielOperationalModes")
    if [r[0] for r in base_modes] != ["TEACH-AIR-01", "POS-A", "POS-B", "POS-C", "POS-D"]:
        raise ValueError("accepted materiel modes changed")
    if rows(doc, "OperationalModes") != [["G04-OPS", "Two-position mission RBD", None]]:
        raise ValueError("accepted mode definition changed")
    if [r[2] for r in rows(doc, "FailureMode")] != ["POS-A", "POS-B"]:
        raise ValueError("accepted failure modes changed")
    mother = arm == "mother75"
    mode_id = "G08-A-75" if mother else "G08-B-75"
    position = "POS-A" if mother else "POS-B"
    rows(doc, "ProblemDescription")[0][0] = f"G08.var05 tree {position} selected usage 0.75 via {'MBOPM' if mother else 'SBOPM'}"
    rows(doc, "OperationalModes").append([mode_id, f"Tree {position} 0.75-rate usage", None])
    base_modes.append([position, mode_id, None, None, 0.75, None])
    if mother:
        for edge in tree:
            edge[3] = mode_id
    else:
        tree[0][4] = mode_id
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
