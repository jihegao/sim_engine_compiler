"""Remove only the PAR-MISSION mode assignment from accepted G09.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G09-var01-mission-rbd-v1.0.0" / "mixed-input.json"
PARENT_SHA = "62e48b3eae86e0713e0a5c641ec28dddc3cc3cd81dc99be2659ceeee2f63475b"


def rows(doc: dict, name: str) -> list[list]:
    hits = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(hits) != 1 or len(hits[0]["instances"]) != 1:
        raise ValueError(name)
    return hits[0]["instances"][0]["rows"]


def make() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G09.var01 mixed parent changed")
    doc = copy.deepcopy(json.loads(raw))
    modes = rows(doc, "MissionOperationalModes")
    if modes != [["BASIC-MISSION", "TEACH-AIR-01", "G09-SER-OPS", None],
                 ["PAR-MISSION", "TEACH-AIR-01", "G04-OPS", None]]:
        raise ValueError("accepted mission modes changed")
    if [(r[1], r[2]) for r in rows(doc, "OperationProfile")] != [
        ("BASIC-MISSION", 8.0), ("PAR-MISSION", 20.0), ("BASIC-MISSION", 32.0)
    ]:
        raise ValueError("accepted mission schedule changed")
    if [r[2] for r in rows(doc, "FailureMode")] != ["POS-A", "POS-B"]:
        raise ValueError("accepted physical failures changed")
    rows(doc, "ProblemDescription")[0][0] = "G09.var02 PAR-MISSION mode omitted: native DEFAULT series check"
    modes.pop()
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    path = HERE / "default-input.json"
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen default input differs")
    print(json.dumps({"default_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
