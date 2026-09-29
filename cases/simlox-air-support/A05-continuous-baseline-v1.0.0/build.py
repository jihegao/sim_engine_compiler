"""Freeze paired fixed, continuous and initial-shortage A05 inputs from A03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
NAMES = {"fixed": "native-fixed-control.json", "continuous": "native-continuous.json",
         "shortage": "native-initial-shortage.json"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    return matches[0]


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    t = table(doc, name)
    cols = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or field not in cols or rows[0][cols.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    rows[0][cols.index(field)] = after


def build() -> dict[str, dict]:
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError("accepted A03 parent fingerprint differs")
    fixed = copy.deepcopy(json.loads(parent_raw))
    set_one(fixed, "ProblemDescription", "PDESC",
            "A03 two-aircraft, one-wave teaching case; no J35/F35 equivalence",
            "A05 fixed four-hour two-aircraft control")
    set_one(fixed, "Unit", "DESCR", "One-aircraft teaching unit", "Two-aircraft teaching unit")
    set_one(fixed, "MissionType", "DESCR", "Two-hour generic mission", "Four-hour teaching mission")
    set_one(fixed, "MissionType", "DURN", 2, 4.0)
    set_one(fixed, "Control", "SIMPE", 36, 16.0)
    set_one(fixed, "Control", "RCEND", 36, 16.0)
    rc = table(fixed, "ResultCollection")
    cols = [c["name"] for c in rc["columns"]]
    rows = rc["instances"][0]["rows"]
    if len(rows) != 2 or [r[cols.index("RCEND")] for r in rows] != [36, 36]:
        raise ValueError("unexpected A03 result windows")
    for row in rows:
        row[cols.index("RCEND")] = 16.0
    continuous = copy.deepcopy(fixed)
    set_one(continuous, "ProblemDescription", "PDESC",
            "A05 fixed four-hour two-aircraft control",
            "A05 continuous four-hour two-aircraft control")
    set_one(continuous, "MissionType", "MPAT", None, "CONTINUOUS")
    shortage = copy.deepcopy(continuous)
    set_one(shortage, "ProblemDescription", "PDESC",
            "A05 continuous four-hour two-aircraft control",
            "A05 continuous four-hour initial one-aircraft shortage")
    set_one(shortage, "Unit", "DESCR", "Two-aircraft teaching unit", "One-aircraft teaching unit")
    set_one(shortage, "SystemDeployment", "QTYPS", 2, 1)
    return {"fixed": fixed, "continuous": continuous, "shortage": shortage}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    outputs = {}
    for key, doc in build().items():
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / NAMES[key]
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {key} input differs")
        outputs[key] = sha(raw)
    print(json.dumps(outputs))


if __name__ == "__main__":
    main()
