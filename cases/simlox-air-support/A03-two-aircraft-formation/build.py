"""Build the minimal A03 native input from the frozen A02 teaching case."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA256 = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(document: dict, name: str) -> dict:
    found = [item for item in document["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return found[0]


def rows(document: dict, name: str) -> list[dict]:
    target = table(document, name)
    columns = [column["name"] for column in target["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in target["instances"][0]["rows"]]


def replace_rows(document: dict, name: str, values: list[dict]) -> None:
    target = table(document, name)
    columns = [column["name"] for column in target["columns"]]
    if any(set(value) != set(columns) for value in values):
        raise ValueError(f"{name}: column mismatch")
    target["instances"][0]["rows"] = [[value[column] for column in columns] for value in values]


def build() -> dict:
    if sha256(PARENT) != PARENT_SHA256:
        raise ValueError("frozen A02 parent input changed")
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    model = copy.deepcopy(parent)
    deployment = rows(model, "SystemDeployment")
    mission = rows(model, "MissionType")
    schedule = rows(model, "OperationProfile")
    if len(deployment) != 1 or deployment[0]["QTYPS"] != 1:
        raise ValueError("unexpected A02 deployment")
    if len(mission) != 1 or (mission[0]["NOS"], mission[0]["MNOS"]) != (1, 1):
        raise ValueError("unexpected A02 mission quantity")
    if [row["STIM"] for row in schedule] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected A02 schedule")
    deployment[0]["QTYPS"] = 2
    mission[0]["NOS"] = mission[0]["MNOS"] = 2
    replace_rows(model, "SystemDeployment", deployment)
    replace_rows(model, "MissionType", mission)
    replace_rows(model, "OperationProfile", schedule[:1])
    if sorted(changed_tables(parent, model)) != ["MissionType", "OperationProfile", "SystemDeployment"]:
        raise ValueError("A03 changed an unexpected table")
    return model


def changed_tables(parent: dict, child: dict) -> dict:
    names = [item["name"] for item in parent["model"]["tables"]]
    return {name: {"parent_rows": rows(parent, name), "child_rows": rows(child, name)}
            for name in names if rows(parent, name) != rows(child, name)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    model = build()
    raw = (json.dumps(model, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "native-input.json"
    if args.check:
        if not output.is_file() or output.read_bytes() != raw:
            raise ValueError("A03 checked native input differs from frozen builder")
    else:
        output.write_bytes(raw)
    print(json.dumps({"parent_sha256": PARENT_SHA256, "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "changed_tables": sorted(changed_tables(json.loads(PARENT.read_text()), model))}))


if __name__ == "__main__":
    main()
