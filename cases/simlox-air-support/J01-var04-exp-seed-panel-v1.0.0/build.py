"""Generate a source-pinned twelve-seed EXP preparation panel."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J01-var01-determ-preparation-v1.0.0/native-input.json"
PARENT_SHA256 = "b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409"
SEEDS = tuple(range(1, 13))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected exactly one {name} table and instance")
    return found[0]


def rows(item: dict) -> list[dict]:
    names = [column["name"] for column in item["columns"]]
    return [dict(zip(names, row, strict=True)) for row in item["instances"][0]["rows"]]


def encoded(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def changed(before: dict, after: dict) -> dict:
    result = {}
    source = before["model"]["tables"]
    target = after["model"]["tables"]
    if [x["name"] for x in source] != [x["name"] for x in target]:
        raise ValueError("table topology changed")
    for a, b in zip(source, target, strict=True):
        if a != b:
            if a["columns"] != b["columns"]:
                raise ValueError(f"schema changed: {a['name']}")
            result[a["name"]] = {"before": rows(a), "after": rows(b)}
    return result


def build() -> tuple[dict[str, bytes], bytes]:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted J01.var01 parent changed")
    parent = json.loads(raw)
    if rows(table(parent, "TimeDistributions")) != [{
        "DISTID": "PREP-DET", "PFAC": 1.0, "BASED": "<DETERM>",
        "PARAM1": 0.5, "PARAM2": None, "PARAM3": None, "NOTE": None,
    }]:
        raise ValueError("parent distribution differs")
    if rows(table(parent, "Control"))[0]["NREPS"] != 1:
        raise ValueError("parent repetition count differs")
    outputs: dict[str, bytes] = {}
    docs = {}
    for seed in SEEDS:
        doc = copy.deepcopy(parent)
        control = table(doc, "Control")
        control_row = rows(control)
        if len(control_row) != 1 or control_row[0]["RSEED"] != "1":
            raise ValueError("parent seed differs")
        control["instances"][0]["rows"][0][2] = str(seed)
        prep = table(doc, "MissionPreparation")
        if rows(prep)[0]["DURN"] != 0.5 or rows(prep)[0]["DURND"] != "PREP-DET":
            raise ValueError("parent preparation differs")
        prep["instances"][0]["rows"][0][5] = "PREP-EXP"
        table(doc, "TimeDistributions")["instances"][0]["rows"] = [
            ["PREP-EXP", 1.0, "<EXP>", 0.5, None, None, None]
        ]
        name = f"seed-{seed:02d}-input.json"
        outputs[name] = encoded(doc)
        docs[seed] = doc
    if set(changed(parent, docs[1])) != {"MissionPreparation", "TimeDistributions"}:
        raise ValueError("seed 1 distribution delta differs")
    for seed in SEEDS[1:]:
        if set(changed(docs[1], docs[seed])) != {"Control"}:
            raise ValueError(f"seed {seed} has non-seed delta")
    diff = {
        "schema": "simlox-j01-var04-seed-panel-exact-diff/v1",
        "case_id": "J01", "variant_id": "J01.var04", "version": "1.0.0",
        "parent_case": "J01.var01@1.0.0", "parent_input_sha256": PARENT_SHA256,
        "seed_panel": list(SEEDS), "input_sha256": {name: sha(raw) for name, raw in outputs.items()},
        "parent_to_seed_01": changed(parent, docs[1]),
        "seed_01_to_seed_02": changed(docs[1], docs[2]),
        "other_seed_changes_only_control_rseed": True,
    }
    return outputs, encoded(diff)


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
