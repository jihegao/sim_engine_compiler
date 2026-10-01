"""Build the J01.var01 deterministic preparation probe from accepted B01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "B01-fixed-preparation-v1.0.1" / "native-input.json"
PARENT_SHA256 = "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b"
DISTID = "PREP-DET"


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


def build() -> tuple[bytes, bytes]:
    raw = PARENT.read_bytes()
    if sha256(raw) != PARENT_SHA256:
        raise ValueError("accepted B01 input fingerprint changed")
    parent = json.loads(raw)
    child = copy.deepcopy(parent)
    prep = table(child, "MissionPreparation")
    if rows(prep) != [{
        "MTID": "BASIC-MISSION", "SID": "TEACH-AIR-01", "STID": "BASE-01",
        "DURN": 0.5, "TID": "PREP-FIXED", "DURND": None, "NOTE": None,
    }]:
        raise ValueError("B01 preparation row changed")
    prep_before = rows(table(parent, "MissionPreparation"))
    prep["instances"][0]["rows"][0][5] = DISTID
    distribution = {
        "columns": [
            {"datatype": datatype, "name": name}
            for name, datatype in (
                ("DISTID", "string"), ("PFAC", "double"), ("BASED", "string"),
                ("PARAM1", "double"), ("PARAM2", "double"), ("PARAM3", "double"),
                ("NOTE", "string"),
            )
        ],
        "instances": [{"instance_name": "", "rows": [[DISTID, 1.0, "<DETERM>", 0.5, None, None, None]]}],
        "name": "TimeDistributions",
    }
    if any(item["name"] == "TimeDistributions" for item in child["model"]["tables"]):
        raise ValueError("B01 already defines time distributions")
    child["model"]["tables"].append(distribution)
    if rows(table(child, "MissionPreparation"))[0]["DURND"] != DISTID:
        raise ValueError("distribution reference not set")
    if len(child["model"]["tables"]) != len(parent["model"]["tables"]) + 1:
        raise ValueError("unexpected table count")
    for before, after in zip(parent["model"]["tables"], child["model"]["tables"][:-1], strict=True):
        if before["name"] == "MissionPreparation":
            continue
        if before != after:
            raise ValueError(f"unexpected parent change in {before['name']}")
    child_raw = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {
        "schema": "simlox-j01-var01-exact-parent-diff/v1",
        "parent_case": "B01@1.0.1", "case_id": "J01", "variant_id": "J01.var01", "version": "1.0.0",
        "parent_input_sha256": PARENT_SHA256, "child_input_sha256": sha256(child_raw),
        "modified_tables_only": ["MissionPreparation"], "added_tables_only": ["TimeDistributions"],
        "removed_rows": 0, "added_rows": 1,
        "mission_preparation": {"parent_rows": prep_before, "child_rows": rows(prep)},
        "time_distributions": rows(distribution),
    }
    diff_raw = (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return child_raw, diff_raw


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    child, diff = build()
    for path, raw in ((HERE / "native-input.json", child), (HERE / "parent-diff.json", diff)):
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError(f"checked file differs from builder: {path}")
        else:
            path.write_bytes(raw)
    print(json.dumps({"input_sha256": sha256(child), "parent_diff_sha256": sha256(diff)}))


if __name__ == "__main__":
    main()
