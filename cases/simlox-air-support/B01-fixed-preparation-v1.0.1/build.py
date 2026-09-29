"""Build B01 1.0.1 from the SHA-pinned A01 input, adding two rows only."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA256 = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
PREPARATION = {
    "MTID": "BASIC-MISSION",
    "SID": "TEACH-AIR-01",
    "STID": "BASE-01",
    "DURN": 0.5,
    "TID": "PREP-FIXED",
    "DURND": None,
    "NOTE": None,
}
TASK = {
    "TID": "PREP-FIXED",
    "DESCR": "Fixed 30-minute BASIC-MISSION preparation",
    "TCID": None,
    "TLID": None,
    "NOTE": None,
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(document: dict, name: str) -> dict:
    matches = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected exactly one {name} table and instance")
    return matches[0]


def columns(item: dict) -> list[str]:
    return [column["name"] for column in item["columns"]]


def rows(item: dict) -> list[dict]:
    names = columns(item)
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def build() -> tuple[bytes, bytes]:
    parent_raw = PARENT.read_bytes()
    if sha256(parent_raw) != PARENT_SHA256:
        raise ValueError("frozen A01 native input hash changed")
    parent = json.loads(parent_raw)
    candidate = copy.deepcopy(parent)
    for name, expected in (("MissionPreparation", PREPARATION), ("Tasks", TASK)):
        source = table(parent, name)
        target = table(candidate, name)
        if source["instances"][0]["rows"]:
            raise ValueError(f"A01 {name} is not empty")
        if set(columns(target)) != set(expected) or len(columns(target)) != len(expected):
            raise ValueError(f"unexpected {name} columns")
        target["instances"][0]["rows"].append([expected[column] for column in columns(target)])

    original_tables = parent["model"]["tables"]
    revised_tables = candidate["model"]["tables"]
    if [item["name"] for item in original_tables] != [item["name"] for item in revised_tables]:
        raise ValueError("table order changed")
    changed = {}
    for before, after in zip(original_tables, revised_tables, strict=True):
        if before != after:
            if before["columns"] != after["columns"] or before["name"] != after["name"]:
                raise ValueError("table schema changed")
            changed[before["name"]] = {"parent_rows": rows(before), "child_rows": rows(after)}
    if set(changed) != {"MissionPreparation", "Tasks"}:
        raise ValueError(f"unexpected A01 parent diff: {sorted(changed)}")
    if rows(table(candidate, "MissionPreparation")) != [PREPARATION]:
        raise ValueError("preparation row mismatch")
    if rows(table(candidate, "Tasks")) != [TASK]:
        raise ValueError("task row mismatch")
    candidate_raw = (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {
        "schema": "simlox-b01-exact-parent-diff/v1",
        "parent_case": "A01@1.0.0",
        "case_id": "B01",
        "version": "1.0.1",
        "parent_input_sha256": PARENT_SHA256,
        "child_input_sha256": sha256(candidate_raw),
        "unchanged_table_count": len(original_tables) - len(changed),
        "changed_tables_only": ["MissionPreparation", "Tasks"],
        "field_changes": 0,
        "removed_rows": 0,
        "added_rows": 2,
        "tables": changed,
    }
    diff_raw = (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return candidate_raw, diff_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    candidate, diff = build()
    outputs = {HERE / "native-input.json": candidate, HERE / "parent-diff.json": diff}
    for path, raw in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError(f"checked file differs from builder: {path}")
        else:
            path.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA256, "input_sha256": sha256(candidate),
                      "parent_diff_sha256": sha256(diff), "changed_tables": ["MissionPreparation", "Tasks"]}))


if __name__ == "__main__":
    main()
