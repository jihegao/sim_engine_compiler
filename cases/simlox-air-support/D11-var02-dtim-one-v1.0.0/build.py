"""Derive MISSIONS=4, DTIM=1 from the six-mission control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D11-var02-dtim-control-v1.0.0" / "native-input.json"
PARENT_SHA = "29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table and instance required")
    return found[0]


def put(t: dict, **changes: object) -> None:
    names = [x["name"] for x in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"one {t['name']} row required")
    for name, value in changes.items():
        rows[0][names.index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("frozen D11.var02 control differs")
    doc = copy.deepcopy(json.loads(raw))
    put(table(doc, "ProblemDescription"), PDESC="D11 six-mission DTIM 1 deferment boundary")
    put(table(doc, "MaterielPM"), DTIM=1.0)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen control input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
