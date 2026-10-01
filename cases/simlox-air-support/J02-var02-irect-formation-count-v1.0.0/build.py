"""Build an A03-derived fixed-time 32-seed integer rectangular count panel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A03-two-aircraft-formation-v1.0.1/native-input.json"
PARENT_SHA256 = "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"
SEEDS = tuple(range(1, 33))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table/instance")
    return found[0]


def rows(item: dict) -> list[dict]:
    names = [column["name"] for column in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def field(doc: dict, name: str, column: str, value: object) -> None:
    item = table(doc, name)
    if len(item["instances"][0]["rows"]) != 1:
        raise ValueError(f"expected one row in {name}")
    columns = [part["name"] for part in item["columns"]]
    item["instances"][0]["rows"][0][columns.index(column)] = value


def encode(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def changed(before: dict, after: dict) -> dict:
    first = {item["name"]: item for item in before["model"]["tables"]}
    second = {item["name"]: item for item in after["model"]["tables"]}
    return {name: {"before": rows(first[name]) if name in first else None,
                   "after": rows(second[name]) if name in second else None}
            for name in sorted(first.keys() | second.keys()) if first.get(name) != second.get(name)}


def build() -> tuple[dict[str, bytes], bytes]:
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA256:
        raise ValueError("accepted A03 parent changed")
    parent = json.loads(parent_raw)
    if rows(table(parent, "OperationProfile")) != [{
        "PRID": "BASIC-SCHEDULE", "SPRID": "BASIC-MISSION", "STIM": 8.0,
        "ITYPE": "SCHEDULED", "IQTY": 1, "IQTYD": None, "IPER": 0,
        "IDISP": None, "DTIM": 1 / 3, "XCOORD": None,
        "YCOORD": None, "NOTE": None,
    }]:
        raise ValueError("A03 operation profile differs")
    integer = {
        "columns": [{"datatype": kind, "name": name} for kind, name in (
            ("string", "DISTID"), ("double", "PFAC"), ("string", "BASED"),
            ("double", "PARAM1"), ("double", "PARAM2"), ("double", "PARAM3"),
            ("string", "NOTE"),
        )],
        "instances": [{"instance_name": "", "rows": [
            ["COUNT03", 1.0, "<IRECT>", 0.0, 3.0, None, None]
        ]}],
        "name": "IntegerDistributions",
    }
    if any(item["name"] == "IntegerDistributions" for item in parent["model"]["tables"]):
        raise ValueError("parent unexpectedly has IntegerDistributions")
    outputs: dict[str, bytes] = {}
    docs: dict[int, dict] = {}
    for seed in SEEDS:
        doc = copy.deepcopy(parent)
        field(doc, "Control", "RSEED", str(seed))
        field(doc, "SystemDeployment", "QTYPS", 6)
        field(doc, "OperationProfile", "ITYPE", "RANDOM")
        field(doc, "OperationProfile", "IQTYD", "COUNT03")
        field(doc, "OperationProfile", "IDISP", "EQUIDIST")
        doc["model"]["tables"].append(copy.deepcopy(integer))
        name = f"seed-{seed:02d}-input.json"
        outputs[name] = encode(doc)
        docs[seed] = doc
    expected = {"SystemDeployment", "OperationProfile", "IntegerDistributions"}
    if set(changed(parent, docs[1])) != expected:
        raise ValueError("parent-to-panel table set differs")
    if set(changed(docs[1], docs[2])) != {"Control"}:
        raise ValueError("seed change includes another table")
    for seed in SEEDS[1:]:
        if set(changed(docs[1], docs[seed])) != {"Control"}:
            raise ValueError(f"seed {seed} has a non-seed delta")
    diff = {
        "schema": "simlox-j02-var02-irect-count-exact-diff/v1",
        "case_id": "J02", "variant_id": "J02.var02", "version": "1.0.0",
        "parent_case": "A03@1.0.1", "parent_input_sha256": PARENT_SHA256,
        "seed_panel": list(SEEDS),
        "input_sha256": {name: sha(raw) for name, raw in outputs.items()},
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
