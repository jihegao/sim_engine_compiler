"""Derive the traditional item clock input matrix from accepted D01 LRU."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
VARIANTS = ("item-calhours", "item-missions", "rate-ophours",
            "rate-calhours", "rate-missions")


def table(tables: list[dict], name: str) -> dict:
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def new_table(name: str, spec: list[tuple[str, str, bool]], rows: list[list]) -> dict:
    columns = []
    for field, datatype, key in spec:
        column = {"datatype": datatype}
        if key:
            column["key"] = True
        column["name"] = field
        columns.append(column)
    if any(len(row) != len(columns) for row in rows):
        raise ValueError(f"nonrectangular {name}")
    return {"columns": columns, "instances": [{"instance_name": "", "rows": rows}],
            "name": name}


def build(variant: str, parent_raw: bytes) -> dict:
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant}")
    doc = copy.deepcopy(json.loads(parent_raw))
    tables = doc["model"]["tables"]
    desc = table(tables, "ProblemDescription")
    desc["instances"][0]["rows"][0][0] = f"D02.var06 traditional clock input: {variant}"
    if variant.startswith("item-"):
        item = table(tables, "Item")
        names = [c["name"] for c in item["columns"]]
        records = item["instances"][0]["rows"]
        if len(records) != 1 or records[0][names.index("OPID")] != "OPHOURS":
            raise ValueError("unexpected parent Item.OPID")
        records[0][names.index("OPID")] = variant.removeprefix("item-").upper()
    else:
        if any(t["name"] == "ItemFailureRate" for t in tables):
            raise ValueError("parent already has ItemFailureRate")
        clock = variant.removeprefix("rate-").upper()
        tables.append(new_table("ItemFailureRate", [
            ("IID", "string", True), ("OPID", "string", True),
            ("FRT", "double", False), ("NOTE", "string", False),
        ], [["TEACH-LRU-01", clock, 300000.0, None]]))
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D01 LRU parent fingerprint differs")
    output = {}
    for variant in VARIANTS:
        raw = (json.dumps(build(variant, parent_raw), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{variant}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {variant} input differs")
        output[variant] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "D02", "variant_id": "D02.var06",
                      "parent_sha256": PARENT_SHA, "input_sha256": output}))


if __name__ == "__main__":
    main()
