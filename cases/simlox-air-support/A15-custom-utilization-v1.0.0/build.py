"""Freeze equal custom KM exposure from per-hour and per-mission rates."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
VARIANTS = {"per-hour": (60.0, "1/HOUR"), "per-mission": (120.0, "1/MISSION")}


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published A01 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = f"A15 custom KM mission utilization: {variant}"
    parameter = table(doc, "OperationParameter")
    parameter["instances"][0]["rows"] = [["KM", "Custom distance in kilometres", None]]
    rate, unit = VARIANTS[variant]
    utilization = {
        "name": "MissionTypeUtilization",
        "columns": [
            {"datatype": "string", "key": True, "name": "MTID"},
            {"datatype": "string", "key": True, "name": "SID"},
            {"datatype": "string", "key": True, "name": "OPID"},
            {"datatype": "double", "name": "UTIL"},
            {"datatype": "string", "name": "UTILU"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [["BASIC-MISSION", "TEACH-AIR-01", "KM", rate, unit, None]]}],
    }
    names = [t["name"] for t in doc["model"]["tables"]]
    if "MissionTypeUtilization" in names:
        raise ValueError("parent unexpectedly has MissionTypeUtilization")
    doc["model"]["tables"].insert(names.index("OperationParameter") + 1, utilization)
    return doc


def main() -> None:
    for variant in VARIANTS:
        data = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f"frozen input differs: {variant}")
        path.write_bytes(data)
        print(variant, hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
