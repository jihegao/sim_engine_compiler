"""Add custom KM utilization to the accepted two unit-owned J07 model.

Two paired inputs swap hourly and per-mission rates between units. The only
source differences from J07 are ProblemDescription, OperationParameter, and
MissionTypeUtilization; the pair differs only in description and rate rows.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J07-unit-type-report-v1.0.0" / "native-input.json"
PARENT_SHA = "5609881f54c47c024b1b41f338bf0dd0e04e20e49a41d42b1a81642bdab54f55"
VARIANTS = {
    "a-hour-b-mission": ((60.0, "1/HOUR"), (120.0, "1/MISSION")),
    "a-mission-b-hour": ((120.0, "1/MISSION"), (60.0, "1/HOUR")),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    matches = [t for t in document["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1
    return matches[0]


def build(variant: str) -> dict:
    assert variant in VARIANTS
    parent_bytes = PARENT.read_bytes()
    assert sha(parent_bytes) == PARENT_SHA
    document = copy.deepcopy(json.loads(parent_bytes))
    table(document, "ProblemDescription")["instances"][0]["rows"][0][0] = f"A15 two unit-owned KM missions: {variant}"
    operation_parameter = table(document, "OperationParameter")
    assert operation_parameter["instances"][0]["rows"] == [[None, None, None]]
    operation_parameter["instances"][0]["rows"] = [["KM", "Abstract custom mission exposure", None]]
    names = [t["name"] for t in document["model"]["tables"]]
    assert "MissionTypeUtilization" not in names
    rate_a, rate_b = VARIANTS[variant]
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
        "instances": [{"instance_name": "", "rows": [
            ["MISSION-A", "TEACH-AIR-01", "KM", rate_a[0], rate_a[1], None],
            ["MISSION-B", "TEACH-AIR-01", "KM", rate_b[0], rate_b[1], None],
        ]}],
    }
    document["model"]["tables"].insert(names.index("OperationParameter") + 1, utilization)
    assert len(document["model"]["tables"]) == len(names) + 1
    return document


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    for variant in VARIANTS:
        data = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"{variant}-input.json"
        if args.write:
            if path.exists():
                assert path.read_bytes() == data, f"frozen input differs: {path}"
            else:
                path.write_bytes(data)
        else:
            assert path.read_bytes() == data, f"frozen input differs: {path}"
        print(variant, sha(data), len(data))


if __name__ == "__main__":
    main()
