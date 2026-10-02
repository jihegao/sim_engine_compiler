"""Move the first failing physical position onto the bridge block."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "G07-four-path-panel-v1.0.0" / "allbroken-input.json"
PARENT_SHA = "347790dfeb69c932398e366dd71fca4aff142cd5a506171a057222518046ed52"
CONTROL = ROOT / "G07-four-path-panel-v1.0.0" / "ulur-input.json"
CONTROL_SHA = "de2048592999168639e3b9c5672c41b9c8acf924e940ee1b90a927099cd1354c"
PATHS = (("UL", "UR"), ("LL", "LR"), ("UL", "BR", "LR"), ("LL", "BR", "UR"))
SLOTS = ("UL", "LL", "BR", "UR", "LR")
MAPPING = {"UL": "E", "LL": "A", "BR": "B", "UR": "C", "LR": "D"}


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def live_paths(failed: set[str]) -> list[tuple[str, ...]]:
    return [p for p in PATHS if all(MAPPING[slot] not in failed for slot in p)]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted allbroken parent changed")
    if hashlib.sha256(CONTROL.read_bytes()).hexdigest() != CONTROL_SHA:
        raise ValueError("accepted bridge-second comparator changed")
    doc = copy.deepcopy(json.loads(raw))
    rbd = rows(doc, "RBDBridge")
    if len(rbd) != 1 or rbd[0][0] != "G07-BRIDGE" or rbd[0][2:7] != ["POS-B", "POS-A", "POS-E", "POS-C", "POS-D"]:
        raise ValueError("allbroken bridge row changed")
    if [r[0] for r in rows(doc, "FailureMode")] != ["FM-POS-A", "FM-POS-B"]:
        raise ValueError("failure modes changed")
    if live_paths({"B"}) != [("UL", "UR"), ("LL", "LR")]:
        raise ValueError("bridge failure does not leave direct paths")
    if live_paths({"B", "A"}) != [("UL", "UR")]:
        raise ValueError("later A failure does not leave upper route")
    rows(doc, "ProblemDescription")[0][0] = "G07.var03 bridge block B fails first; direct routes remain"
    rbd[0][1] = "Bridge B failure with direct route preserved"
    rbd[0][2:7] = [f"POS-{MAPPING[slot]}" for slot in SLOTS]
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "brfirst-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"brfirst": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
