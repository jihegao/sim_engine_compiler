"""Contrast system OPHOURS PM under BASIC system USERT 0.5 versus 1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G09-var04-usert-boundary-v1.0.1" / "use1-input.json"
PARENT_SHA = "957e7b16a75c2cc06a6bf2ef6a2a7b9ae0a44e683349c248383281b3ffec5c85"
ARMS = {"syshalf": 0.5, "sysfull": 1.0}


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
        raise ValueError("accepted G09.var04 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    modes = rows(doc, "MaterielOperationalModes")
    if modes[3] != ["TEACH-AIR-01", "G09-SER-OPS", "G09-SER-RBD", None, 1.0, None]:
        raise ValueError("parent BASIC system mode changed")
    if modes[0] != ["TEACH-AIR-01", "G04-OPS", "G04-PARALLEL", None, 1.0, None]:
        raise ValueError("parent PAR system mode changed")
    if rows(doc, "MaterielPM") or rows(doc, "PMLocation") or rows(doc, "Tasks") or \
       rows(doc, "SubTaskType") or rows(doc, "TaskBreakDown"):
        raise ValueError("parent already has PM task")
    failure = rows(doc, "FailureMode")
    if [r[3] for r in failure] != [1e-9, 600000.0]:
        raise ValueError("parent physical rates changed")
    if [(r[1], r[2]) for r in rows(doc, "OperationProfile")] != [
        ("BASIC-MISSION", 8.0), ("PAR-MISSION", 20.0), ("BASIC-MISSION", 32.0)
    ]:
        raise ValueError("parent mission schedule changed")
    rows(doc, "ProblemDescription")[0][0] = f"G09.var07 system OPHOURS PM BASIC USERT={ARMS[arm]:g}"
    modes[3][4] = ARMS[arm]
    failure[1][3] = 1e-9  # common positive B suppression; A already positive near-zero
    rows(doc, "Tasks").append(["PM-SYS-OP15", "One-hour OPHOURS service", None, None, None])
    rows(doc, "SubTaskType").append(["INSPECT", "Inspection", None])
    rows(doc, "TaskBreakDown").append(["PM-SYS-OP15", 1, "INSPECT", 1.0, None, None])
    rows(doc, "MaterielPM").append(["SYS-OP15", "System operation-hour PM", "TEACH-AIR-01",
                                    1.5, "OPHOURS", None, 0.0, 0.0, None, None,
                                    None, None, None, None])
    rows(doc, "PMLocation").append(["SYS-OP15", "TEACH-AIR-01", "BASE-01", 1.0,
                                    None, None, "PM-SYS-OP15", None, None])
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
