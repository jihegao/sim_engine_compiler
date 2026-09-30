"""Build A10 default-profile horizon probes from the published A01 input."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
VARIANTS = ("48h", "50h")


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def set_field(tab: dict, field: str, value: object) -> None:
    index = [c["name"] for c in tab["columns"]].index(field)
    for instance in tab["instances"]:
        for row in instance["rows"]:
            row[index] = value


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published A01 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    horizon = 48.0 if variant == "48h" else 50.0
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"A10 default operational profile; one aircraft; {variant} horizon"
    )
    doc["model"]["tables"] = [t for t in doc["model"]["tables"]
                               if t["name"] not in ("MissionType", "OperationProfile", "Operations")]
    set_field(table(doc, "Control"), "SIMPE", horizon)
    set_field(table(doc, "Control"), "RCEND", horizon)
    set_field(table(doc, "ResultCollection"), "RCEND", horizon)
    set_field(table(doc, "SystemDeployment"), "UTIL", 0.25)
    doc["model"]["tables"].append({
        "name": "SystemDeploymentUtilization",
        "columns": [
            {"name": "SID", "datatype": "string", "key": True},
            {"name": "USTID", "datatype": "string", "key": True},
            {"name": "OPID", "datatype": "string", "key": True},
            {"name": "UTIL", "datatype": "double"},
            {"name": "NOTE", "datatype": "string"},
        ],
        "instances": [{"instance_name": "", "rows": [[
            "TEACH-AIR-01", "TEACH-UNIT", "MISSIONS", 1 / 12, None,
        ]]}],
    })
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        target = HERE / f"{variant}-input.json"
        if target.exists():
            if target.read_bytes() != raw:
                raise ValueError(f"frozen {variant} input differs")
        else:
            target.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
