"""Rebuild the two A09 candidate inputs from pinned A02 bytes; no native execution."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
EXPECTED_PARENT_DIFF = {"Control", "OperationProfile", "ProblemDescription", "ResultCollection"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return found[0]


def rows(document: dict, name: str) -> list[dict]:
    item = table(document, name)
    columns = [column["name"] for column in item["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in item["instances"][0]["rows"]]


def set_rows(document: dict, name: str, new_rows: list[dict]) -> None:
    item = table(document, name)
    columns = [column["name"] for column in item["columns"]]
    if len(columns) != len(set(columns)):
        raise ValueError(f"duplicate columns in {name}")
    if any(set(row) != set(columns) for row in new_rows):
        raise ValueError(f"{name} row does not match native schema")
    item["instances"][0]["rows"] = [[row[column] for column in columns] for row in new_rows]


def changed_tables(before: dict, after: dict) -> dict:
    names = [item["name"] for item in before["model"]["tables"]]
    if names != [item["name"] for item in after["model"]["tables"]]:
        raise ValueError("native table layout changed")
    return {name: {"before_rows": rows(before, name), "after_rows": rows(after, name)}
            for name in names if rows(before, name) != rows(after, name)}


def validate_parameters(p: dict) -> None:
    expected = {
        "case_id": "A09", "version": "1.0.0-candidate", "parent_case": "A02@1.0.0",
        "parent_input_sha256": PARENT_SHA256,
        "description": "A09 two-day, two-wave schedule comparison; no J35/F35 equivalence",
        "horizon_hours": 48.0,
        "flat_start_hours": [8.0, 20.0, 32.0, 44.0],
        "daily_start_hours": [8.0, 20.0],
        "repeat_count": 2, "repeat_period_hours": 24.0,
        "root_profile_id": "BASIC-SCHEDULE", "daily_profile_id": "A09-DAILY-TWO-WAVE",
    }
    if p != expected:
        raise ValueError("A09 parameters differ from the reviewed, bounded candidate")
    if p["daily_profile_id"] in {p["root_profile_id"], "BASIC-MISSION"}:
        raise ValueError("profile IDs must not overlap")


def build(p: dict) -> tuple[dict, dict, dict]:
    validate_parameters(p)
    if sha256(PARENT) != PARENT_SHA256:
        raise ValueError("frozen A02 input changed")
    parent = json.loads(PARENT.read_bytes())
    flat = copy.deepcopy(parent)
    control = rows(flat, "Control")
    if len(control) != 1 or control[0]["SIMPE"] != 36.0 or control[0]["RCEND"] != 36.0:
        raise ValueError("unexpected A02 Control window")
    control[0]["SIMPE"] = control[0]["RCEND"] = p["horizon_hours"]
    set_rows(flat, "Control", control)
    result_collection = rows(flat, "ResultCollection")
    if Counter((row["RTYPE"], row["RCEND"]) for row in result_collection) != Counter({("MISSION", 36.0): 1, ("SYSTEM", 36.0): 1}):
        raise ValueError("unexpected A02 result collection")
    for row in result_collection:
        row["RCEND"] = p["horizon_hours"]
    set_rows(flat, "ResultCollection", result_collection)
    set_rows(flat, "ProblemDescription", [{"PDESC": p["description"]}])
    original_profile = rows(parent, "OperationProfile")
    if len(original_profile) != 3 or [r["STIM"] for r in original_profile] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected A02 operation profile")
    if any(r["PRID"] != p["root_profile_id"] or r["SPRID"] != "BASIC-MISSION" or r["ITYPE"] != "SCHEDULED" or r["IQTY"] != 1 or r["IPER"] != 0 for r in original_profile):
        raise ValueError("unexpected A02 profile semantics")
    flat_rows = []
    for hour in p["flat_start_hours"]:
        row = copy.deepcopy(original_profile[0])
        row["STIM"] = hour
        flat_rows.append(row)
    set_rows(flat, "OperationProfile", flat_rows)

    nested = copy.deepcopy(flat)
    root = copy.deepcopy(original_profile[0])
    root.update({"SPRID": p["daily_profile_id"], "STIM": 0.0,
                 "IQTY": p["repeat_count"], "IPER": p["repeat_period_hours"], "DTIM": None})
    nested_rows = [root]
    for hour in p["daily_start_hours"]:
        row = copy.deepcopy(original_profile[0])
        row.update({"PRID": p["daily_profile_id"], "STIM": hour})
        nested_rows.append(row)
    set_rows(nested, "OperationProfile", nested_rows)

    if set(changed_tables(parent, flat)) != EXPECTED_PARENT_DIFF:
        raise ValueError("A02 to flat changed unexpected tables")
    if set(changed_tables(parent, nested)) != EXPECTED_PARENT_DIFF:
        raise ValueError("A02 to nested changed unexpected tables")
    if set(changed_tables(flat, nested)) != {"OperationProfile"}:
        raise ValueError("flat to nested changed more than OperationProfile")
    return parent, flat, nested


def encoded(document: dict) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def artifacts(p: dict) -> dict[str, bytes]:
    parent, flat, nested = build(p)
    output = {
        "native-flat.json": encoded(flat),
        "native-nested.json": encoded(nested),
    }
    for variant, child in (("flat", flat), ("nested", nested)):
        output[f"parent-diff-{variant}.json"] = encoded({
            "parent_case": "A02@1.0.0", "parent_input_sha256": PARENT_SHA256,
            "child_case": f"A09@1.0.0-candidate/{variant}",
            "changed_tables": changed_tables(parent, child),
        })
    output["variant-diff.json"] = encoded({
        "before_variant": "flat", "after_variant": "nested",
        "changed_tables": changed_tables(flat, nested),
    })
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check checked-in candidates without writing")
    args = parser.parse_args()
    p = json.loads((HERE / "parameters.json").read_text(encoding="utf-8"))
    built = artifacts(p)
    for name, raw in built.items():
        path = HERE / name
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError(f"checked {name} differs from pinned A02 builder")
        else:
            path.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA256,
                      "candidate_sha256": {name: hashlib.sha256(raw).hexdigest()
                                           for name, raw in built.items() if name.startswith("native-")},
                      "parent_changed_tables": sorted(EXPECTED_PARENT_DIFF),
                      "variant_changed_tables": ["OperationProfile"]}))


if __name__ == "__main__":
    main()
