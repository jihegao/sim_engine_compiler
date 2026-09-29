"""Derive D02.var04 long direct-CM boundary from accepted D06."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
CHILD = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    return matches[0]


def build(parent_raw: bytes) -> dict:
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D06 parent fingerprint differs")
    child = copy.deepcopy(json.loads(parent_raw))
    table(child, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "D02.var04 position A direct CM spans hour-20 scheduled mission")
    cm = table(child, "CMLocation")
    names = [c["name"] for c in cm["columns"]]
    rows = cm["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][names.index("CMT")] != 0.5:
        raise ValueError("unexpected parent direct CM duration")
    rows[0][names.index("CMT")] = 15.5
    return child


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    child = build(PARENT.read_bytes())
    raw = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if CHILD.exists():
            raise FileExistsError(CHILD)
        CHILD.write_bytes(raw)
    elif CHILD.read_bytes() != raw:
        raise ValueError("frozen child input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "child_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
