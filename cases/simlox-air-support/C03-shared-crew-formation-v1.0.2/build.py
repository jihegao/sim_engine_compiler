"""Derive two-aircraft shared-crew variants from published C02 single-both."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C02-joint-resources-v1.0.2" / "inputs" / "single-both.json"
PARENT_SHA256 = "0bf522cd4c4387f110ceae34d7c1e4b4c8b40c8e495e7e27920a48e47bb5f937"
CAPACITIES = {"staffing-2": 2, "staffing-1": 1, "staffing-0": 0}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"missing or duplicate native table: {name}")
    return matches[0]


def rows(item: dict) -> list[dict]:
    names = [column["name"] for column in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def put(doc: dict, name: str, records: list[dict]) -> None:
    item = table(doc, name)
    names = [column["name"] for column in item["columns"]]
    item["instances"][0]["rows"] = [[record[name] for name in names] for record in records]


def build_variant(parent: dict, variant_id: str) -> tuple[bytes, bytes]:
    if variant_id not in CAPACITIES:
        raise ValueError(variant_id)
    child = copy.deepcopy(parent)
    description = rows(table(child, "ProblemDescription"))
    description[0]["PDESC"] = "C03 two-aircraft shared-crew formation; no J35/F35 equivalence"
    put(child, "ProblemDescription", description)
    unit = rows(table(child, "Unit"))
    unit[0]["DESCR"] = "Two-aircraft shared-crew teaching unit"
    put(child, "Unit", unit)
    deployment = rows(table(child, "SystemDeployment"))
    deployment[0]["QTYPS"] = 2
    put(child, "SystemDeployment", deployment)
    mission = rows(table(child, "MissionType"))
    mission[0].update(NOS=2, MNOS=2, DURN=1.0, NOPER=0.5,
                      DESCR="One-hour two-aircraft shared-crew formation")
    put(child, "MissionType", mission)
    profile = rows(table(child, "OperationProfile"))
    profile[0]["DTIM"] = 1.0
    put(child, "OperationProfile", profile)
    preparation = rows(table(child, "MissionPreparation"))
    preparation[0]["DURN"] = 0.5
    put(child, "MissionPreparation", preparation)
    resource = rows(table(child, "Resource"))
    if [row["RID"] for row in resource] != ["P-CREW", "P-OTHER", "E-GSE"]:
        raise ValueError("C02 resource identities changed")
    put(child, "Resource", resource[:1])
    allocation = rows(table(child, "ResourceAllocation"))
    if [(row["RID"], row["RQTY"]) for row in allocation] != [
            ("P-CREW", 1), ("P-OTHER", 0), ("E-GSE", 1)]:
        raise ValueError("C02 resource allocation changed")
    allocation[0]["RQTY"] = CAPACITIES[variant_id]
    put(child, "ResourceAllocation", allocation[:1])
    demand = rows(table(child, "SubTaskResource"))
    if [(row["RID"], row["QTY"]) for row in demand] != [("P-CREW", 1), ("E-GSE", 1)]:
        raise ValueError("C02 joint demand changed")
    put(child, "SubTaskResource", demand[:1])
    before, after = parent["model"]["tables"], child["model"]["tables"]
    if [item["name"] for item in before] != [item["name"] for item in after]:
        raise ValueError("native table order changed")
    changes = {a["name"]: {"parent_rows": rows(a), "child_rows": rows(b)}
               for a, b in zip(before, after, strict=True) if a != b}
    expected = {"ProblemDescription", "Unit", "SystemDeployment", "MissionType",
                "OperationProfile", "MissionPreparation", "Resource",
                "ResourceAllocation", "SubTaskResource"}
    if set(changes) != expected:
        raise ValueError(f"unexpected C02 parent delta: {list(changes)}")
    model = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {"schema": "simlox-c03-exact-parent-diff/v1", "parent_case": "C02@1.0.2/single-both",
            "case_id": "C03", "version": "1.0.2", "variant_id": variant_id,
            "parent_input_sha256": PARENT_SHA256, "child_input_sha256": sha(model),
            "changed_tables_only": list(changes), "unchanged_table_count": len(before)-len(changes),
            "tables": changes}
    return model, (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source = PARENT.read_bytes()
    if sha(source) != PARENT_SHA256:
        raise ValueError("published C02 parent hash changed")
    parent = json.loads(source)
    hashes = {}
    for variant in CAPACITIES:
        model, diff = build_variant(parent, variant)
        paths = ((HERE / "inputs" / f"{variant}.json", model),
                 (HERE / "parent-diffs" / f"{variant}.json", diff))
        for path, data in paths:
            if args.check:
                if path.read_bytes() != data:
                    raise ValueError(f"generated bytes differ: {path}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
        hashes[variant] = {"input_sha256": sha(model), "parent_diff_sha256": sha(diff)}
    print(json.dumps(hashes, ensure_ascii=False))


if __name__ == "__main__":
    main()
