"""Freeze one direct system repair using native predefined <REPAIR>."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
INPUT = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def put(t: dict, row: list, field: str, value: object) -> None:
    row[[c["name"] for c in t["columns"]].index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published D01 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = "B05.var05 direct system repair with one built-in <REPAIR> subtask"
    repair = table(doc, "SystemRepair")
    repair_row = repair["instances"][0]["rows"][0]
    put(repair, repair_row, "DIRPT", 4.0)
    put(repair, repair_row, "DIRPTID", "B05-DIRP")
    tasks = table(doc, "Tasks")
    tasks["instances"][0]["rows"].append(["B05-DIRP", "Direct system repair with native REPAIR step", None, None, None])
    breakdown = table(doc, "TaskBreakDown")
    breakdown["instances"][0]["rows"].append(["B05-DIRP", 1, "<REPAIR>", 0.5, None, None])
    return doc


def main() -> None:
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if INPUT.exists() and INPUT.read_bytes() != data:
        raise ValueError("frozen input differs")
    INPUT.write_bytes(data)
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
