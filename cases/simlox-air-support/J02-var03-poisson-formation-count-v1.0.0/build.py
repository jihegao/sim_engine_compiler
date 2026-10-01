"""Build an accepted-J02-derived 32-seed native integer Poisson count panel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J02-var02-irect-formation-count-v1.0.0/seed-01-input.json"
PARENT_SHA256 = "35e68a4d352d3f4e7ff62d3bd9d2c087ca2510837c33c15ad31a3dfa5d6491fa"
SEEDS = tuple(range(1, 33))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def table(doc: dict, name: str) -> dict:
    items = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(items) != 1 or len(items[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return items[0]


def rows(item: dict) -> list[dict]:
    names = [col["name"] for col in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def field(doc: dict, name: str, column: str, value: object) -> None:
    item = table(doc, name)
    if len(item["instances"][0]["rows"]) != 1:
        raise ValueError(f"expected one {name} row")
    columns = [col["name"] for col in item["columns"]]
    item["instances"][0]["rows"][0][columns.index(column)] = value


def changed(before: dict, after: dict) -> dict:
    old = {item["name"]: item for item in before["model"]["tables"]}
    new = {item["name"]: item for item in after["model"]["tables"]}
    return {name: {"before": rows(old[name]), "after": rows(new[name])}
            for name in sorted(old.keys() | new.keys()) if old.get(name) != new.get(name)}


def build() -> tuple[dict[str, bytes], bytes]:
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA256:
        raise ValueError("accepted J02.var02 parent changed")
    parent = json.loads(parent_raw)
    if rows(table(parent, "IntegerDistributions")) != [{
        "DISTID": "COUNT03", "PFAC": 1.0, "BASED": "<IRECT>",
        "PARAM1": 0.0, "PARAM2": 3.0, "PARAM3": None, "NOTE": None,
    }]:
        raise ValueError("parent integer row differs")
    if rows(table(parent, "OperationProfile"))[0]["IQTYD"] != "COUNT03":
        raise ValueError("parent quantity reference differs")
    outputs: dict[str, bytes] = {}
    docs: dict[int, dict] = {}
    for seed in SEEDS:
        doc = copy.deepcopy(parent)
        field(doc, "Control", "RSEED", str(seed))
        field(doc, "SystemDeployment", "QTYPS", 12)
        field(doc, "OperationProfile", "IQTYD", "COUNTPOI")
        item = table(doc, "IntegerDistributions")
        item["instances"][0]["rows"] = [["COUNTPOI", 1.0, "<POISSON>", 1.5, None, None, None]]
        name = f"seed-{seed:02d}-input.json"
        outputs[name] = encode(doc)
        docs[seed] = doc
    if set(changed(parent, docs[1])) != {"SystemDeployment", "OperationProfile", "IntegerDistributions"}:
        raise ValueError("parent-to-seed01 delta differs")
    for seed in SEEDS[1:]:
        if set(changed(docs[1], docs[seed])) != {"Control"}:
            raise ValueError(f"seed {seed} changes more than Control")
    diff = {
        "schema": "simlox-j02-var03-poisson-count-exact-diff/v1",
        "case_id": "J02", "variant_id": "J02.var03", "version": "1.0.0",
        "parent_case": "J02.var02@1.0.0", "parent_input_sha256": PARENT_SHA256,
        "seeds": list(SEEDS), "input_sha256": {name: sha(raw) for name, raw in outputs.items()},
        "parent_to_seed_01": changed(parent, docs[1]),
        "seed_01_to_seed_02": changed(docs[1], docs[2]),
        "other_seed_changes_only_control_rseed": True,
    }
    return outputs, encode(diff)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs, diff = build()
    outputs["panel-diff.json"] = diff
    for name, raw in outputs.items():
        path = HERE / name
        if args.check:
            if not path.is_file() or path.read_bytes() != raw:
                raise ValueError(f"built output differs: {name}")
        else:
            path.write_bytes(raw)
    print(json.dumps({name: sha(raw) for name, raw in outputs.items()}))


if __name__ == "__main__":
    main()
