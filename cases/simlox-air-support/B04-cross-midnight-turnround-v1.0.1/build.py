"""Build paired B04 cross-midnight turnround inputs from published B02."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
PARENT_SHA = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
VARIANTS = ("control", "turnround")


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build(variant: str) -> dict:
    if variant not in VARIANTS:
        raise ValueError(variant)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published B02 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "B04 v101 cross-midnight missions, no post-flight turnround control" if variant == "control"
        else "B04 v101 cross-midnight missions, one-hour post-flight turnround"
    )
    profile = table(doc, "OperationProfile")
    names = [c["name"] for c in profile["columns"]]
    row = profile["instances"][0]["rows"][0]
    row[names.index("STIM")] = 21.5
    second = copy.deepcopy(row)
    second[names.index("STIM")] = 24.75
    second[names.index("DTIM")] = 1.0
    profile["instances"][0]["rows"].append(second)
    if variant == "turnround":
        doc["model"]["tables"].append({
            "name": "MissionTurnround",
            "columns": [
                {"name": "MTID", "datatype": "string", "key": True},
                {"name": "SID", "datatype": "string", "key": True},
                {"name": "STID", "datatype": "string", "key": True},
                {"name": "DURN", "datatype": "double"},
                {"name": "TID", "datatype": "string"},
                {"name": "DURND", "datatype": "string"},
                {"name": "NOTE", "datatype": "string"},
            ],
            "instances": [{"instance_name": "", "rows": [[
                "BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 1.0, None, None, None,
            ]]}],
        })
    return doc


def main() -> None:
    for variant in VARIANTS:
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / f"{variant}-input.json"
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError(f"frozen {variant} input differs")
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
