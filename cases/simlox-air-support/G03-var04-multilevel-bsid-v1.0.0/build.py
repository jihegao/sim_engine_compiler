"""Build a second-level BSID variant and an invalid-reference control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G03-var03-simultaneous-base-variant-v1.0.0" / "native-input.json"
PARENT_SHA = "42f3d9db9b201b80314731091e3f3e1ea6b5dfefdc40addca5f75f33daf13c7f"
ARMS = ("grandchild", "invalid-reference")


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
        raise ValueError("accepted G03.var03 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    systems, repairs, deployment = (rows(doc, n) for n in ("System", "SystemRepair", "SystemDeployment"))
    if [r[0] for r in systems] != ["TEACH-AIR-01", "TEACH-VAR-ADD"] or systems[1][9] != "TEACH-AIR-01":
        raise ValueError("parent BSID lineage changed")
    if deployment != [["TEACH-VAR-ADD", "TEACH-UNIT", 1, 1, None, None, None],
                      ["TEACH-AIR-01", "TEACH-BASE-UNIT", 1, 1, None, None, None]]:
        raise ValueError("parent deployment changed")
    if len(repairs) != 2 or repairs[1][0:6] != ["TEACH-VAR-ADD", "BASE-01", 0.0, 0.5, 1.0, 1.0]:
        raise ValueError("parent repair changed")
    if rows(doc, "ItemStructure") != [["TEACH-LRU-BASE", "TEACH-AIR-01", 1, 1.0, None, None, None, None, None],
                                      ["TEACH-LRU-ADD", "TEACH-VAR-ADD", 1, 1.0, None, None, None, None, None]]:
        raise ValueError("parent item inheritance changed")
    grand = copy.deepcopy(systems[1])
    grand[0] = "TEACH-VAR-GRAND"
    grand[1] = "Second-level BSID variant"
    grand[9] = "TEACH-VAR-ADD" if arm == "grandchild" else "TEACH-NO-SUCH"
    systems.append(grand)
    repair = copy.deepcopy(repairs[1])
    repair[0] = "TEACH-VAR-GRAND"
    repairs.append(repair)
    deployment[0][0] = "TEACH-VAR-GRAND"
    rows(doc, "ProblemDescription")[0][0] = f"G03.var04 {arm} BSID reference"
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
