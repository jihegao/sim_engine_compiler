"""Build deterministic J02 count and capacity-boundary native inputs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J02-var02-irect-formation-count-v1.0.0/seed-01-input.json"
PARENT_SHA256 = "35e68a4d352d3f4e7ff62d3bd9d2c087ca2510837c33c15ad31a3dfa5d6491fa"
ARMS = {
    "determ-2-seed-01": (2, 6, 1),
    "determ-2-seed-02": (2, 6, 2),
    "zero-six": (0, 6, 1),
    "four-eight": (4, 8, 1),
    "four-six": (4, 6, 1),
}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def table(doc: dict, name: str) -> dict:
    matches = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table and instance")
    return matches[0]


def rows(item: dict) -> list[dict]:
    names = [col["name"] for col in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def field(doc: dict, name: str, column: str, value: object) -> None:
    item = table(doc, name)
    if len(item["instances"][0]["rows"]) != 1:
        raise ValueError(f"expected one {name} row")
    names = [col["name"] for col in item["columns"]]
    item["instances"][0]["rows"][0][names.index(column)] = value


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
        raise ValueError("parent integer distribution differs")
    if rows(table(parent, "OperationProfile"))[0]["IQTYD"] != "COUNT03":
        raise ValueError("parent quantity reference differs")
    outputs: dict[str, bytes] = {}
    docs: dict[str, dict] = {}
    for arm, (count, aircraft, seed) in ARMS.items():
        doc = copy.deepcopy(parent)
        field(doc, "Control", "RSEED", str(seed))
        field(doc, "SystemDeployment", "QTYPS", aircraft)
        field(doc, "OperationProfile", "IQTYD", "COUNTD")
        item = table(doc, "IntegerDistributions")
        item["instances"][0]["rows"] = [["COUNTD", 1.0, "<DETERM>", float(count), None, None, None]]
        outputs[f"{arm}-input.json"] = encode(doc)
        docs[arm] = doc
    if set(changed(parent, docs["determ-2-seed-01"])) != {"OperationProfile", "IntegerDistributions"}:
        raise ValueError("deterministic parent delta differs")
    if set(changed(docs["determ-2-seed-01"], docs["determ-2-seed-02"])) != {"Control"}:
        raise ValueError("seed control delta differs")
    if set(changed(docs["four-eight"], docs["four-six"])) != {"SystemDeployment"}:
        raise ValueError("capacity contrast differs")
    diff = {
        "schema": "simlox-j02-determ-boundary-exact-diff/v1",
        "case_id": "J02", "variant_ids": ["J02.var01", "J02.var04"], "version": "1.0.0",
        "parent_case": "J02.var02@1.0.0", "parent_input_sha256": PARENT_SHA256,
        "arms": {arm: {"count": count, "deployed_aircraft": aircraft, "seed": seed,
                        "input_sha256": sha(outputs[f"{arm}-input.json"]),
                        "parent_delta": changed(parent, docs[arm])}
                 for arm, (count, aircraft, seed) in ARMS.items()},
        "determ_seed_delta": changed(docs["determ-2-seed-01"], docs["determ-2-seed-02"]),
        "capacity_delta": changed(docs["four-eight"], docs["four-six"]),
    }
    return outputs, encode(diff)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs, diff = build()
    outputs["exact-diff.json"] = diff
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
