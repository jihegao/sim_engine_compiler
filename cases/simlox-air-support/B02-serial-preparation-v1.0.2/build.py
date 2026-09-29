"""Build B02 1.0.2 from the published, SHA-pinned B01 1.0.1 input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
PARENT_SHA256 = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
PREP_KEY = {"MTID": "BASIC-MISSION", "SID": "TEACH-AIR-01", "STID": "BASE-01"}
TASK_ID = "PREP-FIXED"  # Retain the published B01 business identity.
STEPS = ((1, "INSPECT", 10), (2, "SERVICE", 20))
CHANGED_TABLES = ("MissionPreparation", "Tasks", "SubTaskType", "TaskBreakDown")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(document: dict, name: str) -> dict:
    matches = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return matches[0]


def columns(item: dict) -> list[str]:
    return [column["name"] for column in item["columns"]]


def rows(item: dict) -> list[dict]:
    names = columns(item)
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def replace_rows(document: dict, name: str, expected_columns: tuple[str, ...], new_rows: list[dict]) -> None:
    target = table(document, name)
    if tuple(columns(target)) != expected_columns:
        raise ValueError(f"{name} schema changed")
    target["instances"][0]["rows"] = [[row[column] for column in expected_columns] for row in new_rows]


def validate_steps(steps: tuple[tuple[int, str, int], ...]) -> None:
    if len(steps) != 2 or [step[0] for step in steps] != [1, 2]:
        raise ValueError("B02 needs exactly two ordered steps with SEQ 1,2")
    if [step[1] for step in steps] != ["INSPECT", "SERVICE"]:
        raise ValueError("B02 step identities changed")
    if any(not isinstance(step[2], int) or step[2] <= 0 for step in steps):
        raise ValueError("B02 step durations must be positive integer minutes")
    if [step[2] for step in steps] != [10, 20]:
        raise ValueError("B02 contracted durations changed")


def build() -> tuple[bytes, bytes]:
    parent_raw = PARENT.read_bytes()
    if sha256(parent_raw) != PARENT_SHA256:
        raise ValueError("published B01 1.0.1 parent input hash changed")
    parent = json.loads(parent_raw)
    candidate = copy.deepcopy(parent)
    validate_steps(STEPS)

    prep = rows(table(parent, "MissionPreparation"))
    tasks = rows(table(parent, "Tasks"))
    if len(prep) != 1 or {key: prep[0][key] for key in PREP_KEY} != PREP_KEY or prep[0]["TID"] != TASK_ID or prep[0]["DURN"] != 0.5:
        raise ValueError("published B01 preparation is not the expected parent")
    if len(tasks) != 1 or tasks[0]["TID"] != TASK_ID or rows(table(parent, "SubTaskType")) or rows(table(parent, "TaskBreakDown")):
        raise ValueError("published B01 task or empty breakdown differs")
    mission = rows(table(parent, "MissionType"))
    if len(mission) != 1 or mission[0]["MTID"] != "BASIC-MISSION" or mission[0]["NOPER"] != 1.0:
        raise ValueError("published B01 one-hour notice differs")

    new_prep = copy.deepcopy(prep)
    new_prep[0]["DURN"] = 0.75  # Deliberately distinct from the 30-minute breakdown.
    new_tasks = copy.deepcopy(tasks)
    new_tasks[0]["DESCR"] = "Serial 10+20-minute BASIC-MISSION preparation"
    subtypes = [{"SUTID": name, "DESCR": name, "NOTE": None} for _, name, _ in STEPS]
    breakdown = [{"TID": TASK_ID, "SEQ": seq, "SUTID": name, "DURN": minutes / 60,
                  "DURND": None, "NOTE": None} for seq, name, minutes in STEPS]
    replace_rows(candidate, "MissionPreparation", ("MTID", "SID", "STID", "DURN", "TID", "DURND", "NOTE"), new_prep)
    replace_rows(candidate, "Tasks", ("TID", "DESCR", "TCID", "TLID", "NOTE"), new_tasks)
    replace_rows(candidate, "SubTaskType", ("SUTID", "DESCR", "NOTE"), subtypes)
    replace_rows(candidate, "TaskBreakDown", ("TID", "SEQ", "SUTID", "DURN", "DURND", "NOTE"), breakdown)

    before = parent["model"]["tables"]
    after = candidate["model"]["tables"]
    if [item["name"] for item in before] != [item["name"] for item in after]:
        raise ValueError("native table order changed")
    changed = {}
    for old, new in zip(before, after, strict=True):
        if old != new:
            if old["name"] != new["name"] or old["columns"] != new["columns"]:
                raise ValueError("native table schema changed")
            changed[old["name"]] = {"parent_rows": rows(old), "child_rows": rows(new)}
    if set(changed) != set(CHANGED_TABLES):
        raise ValueError(f"unexpected B01 parent delta: {sorted(changed)}")

    candidate_raw = (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {
        "schema": "simlox-b02-exact-parent-diff/v1", "parent_case": "B01@1.0.1",
        "case_id": "B02", "version": "1.0.2", "parent_input_sha256": PARENT_SHA256,
        "child_input_sha256": sha256(candidate_raw),
        "unchanged_table_count": len(before) - len(changed),
        "changed_tables_only": list(CHANGED_TABLES), "field_changes": 2,
        "removed_rows": 0, "added_rows": 4, "tables": changed,
    }
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
