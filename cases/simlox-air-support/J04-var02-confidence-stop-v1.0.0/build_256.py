"""Build a confidence-stop diagnostic from accepted J04.var01 seed 1."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J04-var01-fixed-replications-v1.0.0/probe-input.json"
PARENT_SHA256 = "4a4e2df598a515762b1c4de8894c139c6ac6bce40c523d7e5f0720514f7f5579"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    matches = [item for item in doc["model"]["tables"] if item["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table/instance")
    return matches[0]


def rows(item: dict) -> list[dict]:
    columns = [col["name"] for col in item["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in item["instances"][0]["rows"]]


def build() -> tuple[bytes, bytes]:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted parent changed")
    parent = json.loads(raw)
    control = rows(table(parent, "Control"))
    if len(control) != 1 or control[0]["NREPS"] != 16 or control[0]["TCLEV"] != 0 or control[0]["RSEED"] != "1":
        raise ValueError("parent control differs")
    doc = copy.deepcopy(parent)
    item = table(doc, "Control")
    columns = [col["name"] for col in item["columns"]]
    item["instances"][0]["rows"][0][columns.index("NREPS")] = 256
    item["instances"][0]["rows"][0][columns.index("TCLEV")] = 0.09
    old = {t["name"]: t for t in parent["model"]["tables"]}
    new = {t["name"]: t for t in doc["model"]["tables"]}
    if [key for key in old if old[key] != new[key]] != ["Control"]:
        raise ValueError("unexpected table change")
    result = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    diff = {
        "schema": "simlox-j04-var02-confidence-stop-256-exact-diff/v1",
        "parent_case": "J04.var01@1.0.0", "parent_input_sha256": PARENT_SHA256,
        "input_sha256": sha(result), "changed_table": "Control",
        "before": control, "after": rows(item),
    }
    return result, (json.dumps(diff, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source, diff = build()
    for name, raw in (("probe256-input.json", source), ("probe256-diff.json", diff)):
        path = HERE / name
        if args.check:
            if path.read_bytes() != raw:
                raise ValueError(f"source differs: {name}")
        else:
            path.write_bytes(raw)
    print(json.dumps({"probe256-input.json": sha(source), "probe256-diff.json": sha(diff)}))


if __name__ == "__main__":
    main()
