"""Build B03 explicit cold/hot preparation directly from published B02 1.0.2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
PARENT_SHA256 = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
CHANGED_TABLES = ("MissionType", "OperationProfile", "MissionPreparation", "Tasks", "SubTaskType", "TaskBreakDown")
COLD, HOT = "COLD-FIRST", "HOT-SORTIE"
AIRCRAFT, SITE, COLD_TASK, HOT_TASK = "TEACH-AIR-01", "BASE-01", "PREP-FIXED", "HOT-PREP"


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return found[0]


def rows(item: dict) -> list[dict]:
    names = [column["name"] for column in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def replace_rows(document: dict, name: str, new_rows: list[dict]) -> None:
    item = table(document, name)
    names = [column["name"] for column in item["columns"]]
    if any(set(row) != set(names) for row in new_rows):
        raise ValueError(f"{name} row schema differs")
    item["instances"][0]["rows"] = [[row[column] for column in names] for row in new_rows]


def build() -> tuple[bytes, bytes]:
    parent_raw = PARENT.read_bytes()
    if sha256(parent_raw) != PARENT_SHA256:
        raise ValueError("published B02 1.0.2 input hash changed")
    parent = json.loads(parent_raw)
    mission, profile, prep = (rows(table(parent, name)) for name in
                              ("MissionType", "OperationProfile", "MissionPreparation"))
    tasks, subtypes, breakdown = (rows(table(parent, name)) for name in
                                  ("Tasks", "SubTaskType", "TaskBreakDown"))
    if (len(mission) != 1 or mission[0]["MTID"] != "BASIC-MISSION" or mission[0]["NOPER"] != 1.0
            or mission[0]["DURN"] != 2.0 or len(profile) != 1
            or (profile[0]["SPRID"], profile[0]["STIM"]) != ("BASIC-MISSION", 8.0)
            or len(prep) != 1 or (prep[0]["MTID"], prep[0]["SID"], prep[0]["STID"], prep[0]["TID"])
            != ("BASIC-MISSION", AIRCRAFT, SITE, COLD_TASK)
            or len(tasks) != 1 or tasks[0]["TID"] != COLD_TASK
            or [(row["SUTID"], row["DURN"]) for row in breakdown] !=
            [("INSPECT", 10 / 60), ("SERVICE", 20 / 60)]
            or [row["SUTID"] for row in subtypes] != ["INSPECT", "SERVICE"]):
        raise ValueError("published B02 structure differs from required parent")

    candidate = copy.deepcopy(parent)
    cold = dict(mission[0], MTID=COLD, DESCR="Cold-first two-hour sortie")
    hot = dict(mission[0], MTID=HOT, DESCR="Hot two-hour repeat sortie")
    # Keep NOPER=1 hour, DURN=2 hours, and all mission timing parameters.
    replace_rows(candidate, "MissionType", [cold, hot])
    replace_rows(candidate, "OperationProfile", [
        dict(profile[0], SPRID=COLD),
        dict(profile[0], SPRID=HOT, STIM=12.0),
        dict(profile[0], SPRID=HOT, STIM=16.0),
    ])
    replace_rows(candidate, "MissionPreparation", [
        dict(prep[0], MTID=COLD),
        dict(prep[0], MTID=HOT, TID=HOT_TASK, DURN=0.75),
    ])
    replace_rows(candidate, "Tasks", [
        dict(tasks[0], DESCR="Cold-first serial 10+20-minute preparation"),
        dict(tasks[0], TID=HOT_TASK, DESCR="Hot-sortie 10-minute preparation"),
    ])
    replace_rows(candidate, "SubTaskType", subtypes + [
        {"SUTID": "HOT-SERVICE", "DESCR": "HOT-SERVICE", "NOTE": None},
    ])
    replace_rows(candidate, "TaskBreakDown", breakdown + [
        {"TID": HOT_TASK, "SEQ": 1, "SUTID": "HOT-SERVICE", "DURN": 10 / 60,
         "DURND": None, "NOTE": None},
    ])

    before, after = parent["model"]["tables"], candidate["model"]["tables"]
    if [item["name"] for item in before] != [item["name"] for item in after]:
        raise ValueError("native table order changed")
    changed = {}
    for old, new in zip(before, after, strict=True):
        if old != new:
            if old["name"] != new["name"] or old["columns"] != new["columns"]:
                raise ValueError("native schema changed")
            changed[old["name"]] = {"parent_rows": rows(old), "child_rows": rows(new)}
    if tuple(changed) != CHANGED_TABLES:
        raise ValueError(f"unexpected B02 parent delta: {tuple(changed)}")
    candidate_raw = (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {"schema": "simlox-b03-exact-parent-diff/v1", "parent_case": "B02@1.0.2",
            "case_id": "B03", "version": "1.0.2", "parent_input_sha256": PARENT_SHA256,
            "child_input_sha256": sha256(candidate_raw),
            "unchanged_table_count": len(before) - len(changed),
            "changed_tables_only": list(CHANGED_TABLES), "tables": changed}
    diff_raw = (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return candidate_raw, diff_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    candidate, diff = build()
    for path, raw in {HERE / "native-input.json": candidate, HERE / "parent-diff.json": diff}.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError(f"checked file differs from builder: {path}")
        else:
            path.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA256, "input_sha256": sha256(candidate),
                      "parent_diff_sha256": sha256(diff), "changed_tables": CHANGED_TABLES}))


if __name__ == "__main__":
    main()
