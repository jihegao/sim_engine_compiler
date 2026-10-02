"""Freeze explicit versus omitted leaf-LRU prelife from accepted G11.var04."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var04-inherit-item-prelife-v1.0.1" / "native-input-inherited.json"
PARENT_SHA = "473efed447d08808d565d08956b659574596be8e2a8457f451b4816bf50251ae"
ARMS = ("explicit-inherit", "omitted-leaf")


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var04 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "G11.var06 leaf LRU default prelife inheritance; " + arm)
    expected = {
        "Prelife": ["PL-LRU", "Installed monitored item age", "TEACH-LRU-01", None],
        "PrelifeData": ["PL-LRU", "LRU-20", 1, 20.0, None, "CALHOURS", "INHERIT", None],
        "PrelifeStructure": ["PL-LRU", "PL-POS", "POS-INH", None],
    }
    for name, leaf in expected.items():
        rows = table(doc, name)["instances"][0]["rows"]
        if len(rows) != (3 if name != "PrelifeStructure" else 2) or rows[-1] != leaf:
            raise ValueError(f"accepted {name} leaf row differs")
        if arm == "omitted-leaf":
            rows.pop()
    for name in ("Prelife", "PrelifeData", "PrelifeStructure"):
        rows = table(doc, name)["instances"][0]["rows"]
        if any("PL-LRU" in row for row in rows) != (arm == "explicit-inherit"):
            raise ValueError(f"leaf prelife reference remains in {name}")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    shas = {}
    for arm in ARMS:
        encoded = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(encoded)
        elif path.read_bytes() != encoded:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(encoded).hexdigest()
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var06", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
