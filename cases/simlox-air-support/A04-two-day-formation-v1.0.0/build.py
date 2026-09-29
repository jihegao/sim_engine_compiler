"""Derive a two-day, four-wave formation from accepted A03 and A09 inputs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
PROFILE_SOURCE = HERE.parent / "A09-hierarchical-operation-profile-v1.0.1" / "native-nested.json"
PARENT_SHA = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
PROFILE_SHA = "e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85"
CHILD = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    return matches[0]


def rows(doc: dict, name: str) -> tuple[list[str], list[list]]:
    t = table(doc, name)
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def set_one(doc: dict, table_name: str, field: str, before: object, after: object) -> None:
    cols, values = rows(doc, table_name)
    if len(values) != 1 or field not in cols or values[0][cols.index(field)] != before:
        raise ValueError(f"unexpected {table_name}.{field}")
    values[0][cols.index(field)] = after


def build() -> dict:
    parent_raw, profile_raw = PARENT.read_bytes(), PROFILE_SOURCE.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(profile_raw) != PROFILE_SHA:
        raise ValueError("accepted A03 or A09 source fingerprint differs")
    parent = json.loads(parent_raw)
    profile_source = json.loads(profile_raw)
    child = copy.deepcopy(parent)
    set_one(child, "ProblemDescription", "PDESC",
            "A03 two-aircraft, one-wave teaching case; no J35/F35 equivalence",
            "A04 two-day, four-wave, two-aircraft formation teaching case")
    set_one(child, "Unit", "DESCR", "One-aircraft teaching unit", "Two-aircraft teaching unit")
    set_one(child, "Control", "SIMPE", 36, 48.0)
    set_one(child, "Control", "RCEND", 36, 48.0)
    rc_cols, rc_rows = rows(child, "ResultCollection")
    if len(rc_rows) != 2 or [r[rc_cols.index("RTYPE")] for r in rc_rows] != ["MISSION", "SYSTEM"] \
            or [r[rc_cols.index("RCEND")] for r in rc_rows] != [36, 36]:
        raise ValueError("unexpected A03 result windows")
    for row in rc_rows:
        row[rc_cols.index("RCEND")] = 48.0
    a03_cols, a03_rows = rows(child, "OperationProfile")
    a09_cols, a09_rows = rows(profile_source, "OperationProfile")
    if a03_cols != a09_cols or len(a03_rows) != 1 or len(a09_rows) != 3:
        raise ValueError("unexpected profile source shape")
    def view(row: list) -> dict:
        return dict(zip(a03_cols, row, strict=True))
    if (view(a03_rows[0])["STIM"], view(a03_rows[0])["SPRID"]) != (8, "BASIC-MISSION"):
        raise ValueError("unexpected A03 one-wave profile")
    expected = [("BASIC-SCHEDULE", "A09-DAILY-TWO-WAVE", 0, 2, 48),
                ("A09-DAILY-TWO-WAVE", "BASIC-MISSION", 8, 1, 0),
                ("A09-DAILY-TWO-WAVE", "BASIC-MISSION", 20, 1, 0)]
    actual = [(view(r)["PRID"], view(r)["SPRID"], view(r)["STIM"],
               view(r)["IQTY"], view(r)["IPER"]) for r in a09_rows]
    if actual != expected or any(view(r)["ITYPE"] != "SCHEDULED" for r in a09_rows):
        raise ValueError("A09 nested profile differs")
    a03_rows[:] = copy.deepcopy(a09_rows)
    mission_cols, mission_rows = rows(child, "MissionType")
    deployment_cols, deployment_rows = rows(child, "SystemDeployment")
    if (len(mission_rows) != 1 or len(deployment_rows) != 1
            or mission_rows[0][mission_cols.index("NOS")] != 2
            or mission_rows[0][mission_cols.index("MNOS")] != 2
            or deployment_rows[0][deployment_cols.index("QTYPS")] != 2):
        raise ValueError("A03 two-aircraft minimum or deployment differs")
    return child


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if CHILD.exists():
            raise FileExistsError(CHILD)
        CHILD.write_bytes(raw)
    elif CHILD.read_bytes() != raw:
        raise ValueError("frozen A04 input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "profile_source_sha256": PROFILE_SHA,
                      "child_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
