"""Permute the five accepted bridge blocks to expose three remaining paths and all-down."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G07-bridge-diagonal-v1.0.0" / "bridge-input.json"
PARENT_SHA = "ee8ae1ac8deb1edefd9bffca7d1f0f137948ea3d4643b5523635990127d276be"
SLOTS = ("UL", "LL", "BR", "UR", "LR")
PATHS = (("UL", "UR"), ("LL", "LR"), ("UL", "BR", "LR"), ("LL", "BR", "UR"))
ARMS = ("ulur", "lllr", "ulbrlr", "allbroken")
MAPPING = {
    "ulur": {"UL": "C", "LL": "B", "BR": "A", "UR": "D", "LR": "E"},
    "lllr": {"UL": "B", "LL": "C", "BR": "A", "UR": "E", "LR": "D"},
    "ulbrlr": {"UL": "C", "LL": "A", "BR": "D", "UR": "B", "LR": "E"},
    "allbroken": {"UL": "B", "LL": "A", "BR": "E", "UR": "C", "LR": "D"},
}
TARGET = {"ulur": ("UL", "UR"), "lllr": ("LL", "LR"), "ulbrlr": ("UL", "BR", "LR"), "allbroken": None}


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def live_paths(mapping: dict[str, str], failed: set[str]) -> list[tuple[str, ...]]:
    return [p for p in PATHS if all(mapping[slot] not in failed for slot in p)]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted bridge parent changed")
    doc = copy.deepcopy(json.loads(raw))
    original = rows(doc, "RBDBridge")
    if len(original) != 1 or original[0][0] != "G07-BRIDGE" or original[0][2:7] != ["POS-B", "POS-C", "POS-E", "POS-D", "POS-A"]:
        raise ValueError("parent bridge changed")
    if [r[0] for r in rows(doc, "FailureMode")] != ["FM-POS-A", "FM-POS-B"]:
        raise ValueError("parent failure modes changed")
    mapping = MAPPING[arm]
    if set(mapping) != set(SLOTS) or sorted(mapping.values()) != list("ABCDE"):
        raise ValueError("invalid bridge permutation")
    if not live_paths(mapping, {"B"}):
        raise ValueError("first failure must leave a path")
    surviving = live_paths(mapping, {"A", "B"})
    expected = [] if TARGET[arm] is None else [TARGET[arm]]
    if surviving != expected:
        raise ValueError(f"incorrect {arm} paths: {surviving}")
    rows(doc, "ProblemDescription")[0][0] = f"G07 four-path panel: {arm} after matched B/A failures"
    original[0][1] = f"Five-position bridge: {arm} after B/A failures"
    original[0][2:7] = [f"POS-{mapping[slot]}" for slot in SLOTS]
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
            raise ValueError(f"frozen {arm} input differs")
        hashes[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps(hashes))


if __name__ == "__main__":
    main()
