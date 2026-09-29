"""Derive joint personnel/equipment candidates from published C01 1.0.2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C01-personnel-capacity-v1.0.2" / "inputs" / "capacity-2.json"
PARENT_SHA256 = "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c"
VARIANTS = {
    "single-both": (False, 1),
    "single-equipment-zero": (False, 0),
    "serial-both": (True, 1),
    "serial-equipment-zero": (True, 0),
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(document: dict, name: str) -> dict:
    matches = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"missing or duplicate native table: {name}")
    return matches[0]


def rows(item: dict) -> list[dict]:
    names = [column["name"] for column in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def set_rows(document: dict, name: str, records: list[dict]) -> None:
    item = table(document, name)
    columns = [column["name"] for column in item["columns"]]
    item["instances"][0]["rows"] = [[record[column] for column in columns] for record in records]


def build_variant(parent: dict, variant_id: str) -> tuple[bytes, bytes]:
    if variant_id not in VARIANTS:
        raise ValueError(f"unknown C02 variant: {variant_id}")
    serial, equipment_count = VARIANTS[variant_id]
    child = copy.deepcopy(parent)
    resource = rows(table(child, "Resource"))
    if [r["RID"] for r in resource] != ["P-CREW", "P-OTHER"]:
        raise ValueError("published C01 resource identities changed")
    resource.append({"RID": "E-GSE", "DESCR": "Ground support equipment", "PRICE": None,
                     "SUSTC": None, "TLLEN": None, "TYPE": "SPECIAL", "MUTILF": None, "NOTE": None})
    set_rows(child, "Resource", resource)
    allocation = rows(table(child, "ResourceAllocation"))
    if [(r["RID"], r["RQTY"]) for r in allocation] != [("P-CREW", 2), ("P-OTHER", 0)]:
        raise ValueError("published C01 capacity-two allocation changed")
    allocation[0]["RQTY"] = 1
    allocation.append({"POINT": "AIR_BASIC", "RID": "E-GSE", "STID": "BASE-01",
                       "RQTY": equipment_count, "NOTE": None})
    set_rows(child, "ResourceAllocation", allocation)
    demands = rows(table(child, "SubTaskResource"))
    if [(r["SEQ"], r["RID"], r["QTY"]) for r in demands] != [(1, "P-CREW", 2)]:
        raise ValueError("published C01 INSPECT demand changed")
    demands[0]["QTY"] = 1
    demands.append({"TID": "PREP-FIXED", "SEQ": 1, "RID": "E-GSE", "QTY": 1,
                    "RPROB": 1, "ARID": None, "ARTF": None, "ENRMS": None, "NOTE": None})
    set_rows(child, "SubTaskResource", demands)
    if not serial:
        breakdown = rows(table(child, "TaskBreakDown"))
        if [(r["SEQ"], r["SUTID"]) for r in breakdown] != [(1, "INSPECT"), (2, "SERVICE")]:
            raise ValueError("published C01 serial breakdown changed")
        breakdown[0]["DURN"] = 0.5
        set_rows(child, "TaskBreakDown", breakdown[:1])
    before, after = parent["model"]["tables"], child["model"]["tables"]
    if [item["name"] for item in before] != [item["name"] for item in after]:
        raise ValueError("native table order changed")
    changed = {old["name"]: {"parent_rows": rows(old), "child_rows": rows(new)}
               for old, new in zip(before, after, strict=True) if old != new}
    expected = {"Resource", "ResourceAllocation", "SubTaskResource"}
    if not serial:
        expected.add("TaskBreakDown")
    if set(changed) != expected:
        raise ValueError(f"unexpected C01 parent delta: {list(changed)}")
    raw = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {
        "schema": "simlox-c02-exact-parent-diff/v1", "parent_case": "C01@1.0.2/capacity-2",
        "case_id": "C02", "version": "1.0.2", "variant_id": variant_id,
        "parent_input_sha256": PARENT_SHA256, "child_input_sha256": digest(raw),
        "unchanged_table_count": len(before) - len(changed),
        "changed_tables_only": list(changed),
        "added_rows": sum(max(0, len(v["child_rows"]) - len(v["parent_rows"])) for v in changed.values()),
        "removed_rows": sum(max(0, len(v["parent_rows"]) - len(v["child_rows"])) for v in changed.values()),
        "tables": changed,
    }
    return raw, (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build() -> dict[str, tuple[bytes, bytes]]:
    source = PARENT.read_bytes()
    if digest(source) != PARENT_SHA256:
        raise ValueError("published C01 1.0.2 parent hash changed")
    return {variant: build_variant(json.loads(source), variant) for variant in VARIANTS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    hashes = {}
    for variant, (native, diff) in result.items():
        paths = [(HERE / "inputs" / f"{variant}.json", native),
                 (HERE / "parent-diffs" / f"{variant}.json", diff)]
        for path, data in paths:
            if args.check:
                if path.read_bytes() != data:
                    raise ValueError(f"generated bytes differ: {path}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        hashes[variant] = {"input_sha256": digest(native), "parent_diff_sha256": digest(diff)}
    print(json.dumps(hashes, ensure_ascii=False))


if __name__ == "__main__":
    main()
