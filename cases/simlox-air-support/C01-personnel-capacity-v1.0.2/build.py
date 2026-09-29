"""Build four C01 1.0.2 capacity variants from published B02 1.0.2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B02-serial-preparation-v1.0.2" / "native-input.json"
PARENT_SHA256 = "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34"
VARIANTS = {
    "capacity-2": (2, 0),
    "capacity-1": (1, 0),
    "capacity-0": (0, 0),
    "wrong-specialty": (0, 2),
}
CHANGED_TABLES = ("Resource", "ResourceAllocation", "SubTaskResource")


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


def set_rows(document: dict, name: str, expected_columns: tuple[str, ...], new_rows: list[dict]) -> None:
    target = table(document, name)
    if tuple(columns(target)) != expected_columns:
        raise ValueError(f"{name} schema changed")
    if target["instances"][0]["rows"]:
        raise ValueError(f"B02 parent {name} is not empty")
    target["instances"][0]["rows"] = [[row[column] for column in expected_columns] for row in new_rows]


def build_variant(parent: dict, variant_id: str) -> tuple[bytes, bytes]:
    if variant_id not in VARIANTS:
        raise ValueError(f"unknown C01 variant: {variant_id}")
    candidate = copy.deepcopy(parent)
    crew, other = VARIANTS[variant_id]
    resource = [
        {"RID": rid, "DESCR": description, "PRICE": None, "SUSTC": None, "TLLEN": None,
         "TYPE": "SPECIAL", "MUTILF": None, "NOTE": None}
        for rid, description in (("P-CREW", "Crew A personnel"), ("P-OTHER", "Other specialty personnel"))
    ]
    allocation = [
        {"POINT": "AIR_BASIC", "RID": rid, "STID": "BASE-01", "RQTY": quantity, "NOTE": None}
        for rid, quantity in (("P-CREW", crew), ("P-OTHER", other))
    ]
    demand = [{"TID": "PREP-FIXED", "SEQ": 1, "RID": "P-CREW", "QTY": 2,
               "RPROB": 1, "ARID": None, "ARTF": None, "ENRMS": None, "NOTE": None}]
    set_rows(candidate, "Resource", ("RID", "DESCR", "PRICE", "SUSTC", "TLLEN", "TYPE", "MUTILF", "NOTE"), resource)
    set_rows(candidate, "ResourceAllocation", ("POINT", "RID", "STID", "RQTY", "NOTE"), allocation)
    set_rows(candidate, "SubTaskResource", ("TID", "SEQ", "RID", "QTY", "RPROB", "ARID", "ARTF", "ENRMS", "NOTE"), demand)

    before, after = parent["model"]["tables"], candidate["model"]["tables"]
    if [item["name"] for item in before] != [item["name"] for item in after]:
        raise ValueError("native table order changed")
    changed = {}
    for old, new in zip(before, after, strict=True):
        if old != new:
            if old["name"] != new["name"] or old["columns"] != new["columns"]:
                raise ValueError("native table schema changed")
            changed[old["name"]] = {"parent_rows": rows(old), "child_rows": rows(new)}
    if set(changed) != set(CHANGED_TABLES):
        raise ValueError(f"unexpected B02 parent delta: {sorted(changed)}")
    raw = (json.dumps(candidate, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {
        "schema": "simlox-c01-exact-parent-diff/v1", "parent_case": "B02@1.0.2",
        "case_id": "C01", "version": "1.0.2", "variant_id": variant_id,
        "parent_input_sha256": PARENT_SHA256, "child_input_sha256": sha256(raw),
        "unchanged_table_count": len(before) - len(changed),
        "changed_tables_only": list(CHANGED_TABLES), "field_changes": 0,
        "removed_rows": 0, "added_rows": 5, "tables": changed,
    }
    diff_raw = (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return raw, diff_raw


def build() -> dict[str, tuple[bytes, bytes]]:
    parent_raw = PARENT.read_bytes()
    if sha256(parent_raw) != PARENT_SHA256:
        raise ValueError("published B02 1.0.2 parent input hash changed")
    parent = json.loads(parent_raw)
    control = rows(table(parent, "Control"))
    breakdown = rows(table(parent, "TaskBreakDown"))
    if len(control) != 1 or control[0]["APID"] != "AIR_BASIC":
        raise ValueError("B02 Control.APID is not AIR_BASIC")
    if [(row["TID"], row["SEQ"], row["SUTID"], row["DURN"]) for row in breakdown] != [
        ("PREP-FIXED", 1, "INSPECT", 10 / 60), ("PREP-FIXED", 2, "SERVICE", 20 / 60)
    ]:
        raise ValueError("B02 serial breakdown differs")
    if rows(table(parent, "TaskResource")):
        raise ValueError("B02 main task already has resource demand")
    return {variant: build_variant(parent, variant) for variant in VARIANTS}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    for variant, (native, diff) in result.items():
        for path, raw in ((HERE / "inputs" / f"{variant}.json", native),
                          (HERE / "parent-diffs" / f"{variant}.json", diff)):
            if args.check:
                if not path.is_file() or path.read_bytes() != raw:
                    raise ValueError(f"checked file differs from builder: {path}")
            else:
                path.write_bytes(raw)
    print(json.dumps({variant: {"input_sha256": sha256(native), "parent_diff_sha256": sha256(diff)}
                      for variant, (native, diff) in result.items()}))


if __name__ == "__main__":
    main()
