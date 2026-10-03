"""Freeze same-key traditional OPHOURS override on accepted D07.var02."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D07-var02-dual-opid-v1.0.0" / "native-input.json"
PARENT_SHA = "f89c02d4f3868dd97862998685933208145782f283e21da696307a7be017250d"
OUTPUT = HERE / "native-input.json"


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"expected one {name} table")
    return found[0]


def build() -> dict:
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D07.var02 parent changed")
    doc = json.loads(PARENT.read_bytes())
    tables = doc["model"]["tables"]
    table(tables, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "D07.var03 optional OPHOURS rates override base system and item"
    )
    for name, key, id_ in (
        ("ItemFailureRate", "IID", "TEACH-LRU-01"),
        ("SystemFailureRate", "SID", "TEACH-AIR-01"),
    ):
        t = table(tables, name)
        columns = [c["name"] for c in t["columns"]]
        if columns != [key, "OPID", "FRT", "NOTE"] or t["instances"][0]["rows"] != [[id_, "KM", 5000.0, None]]:
            raise ValueError(f"unexpected parent {name} shape")
        t["instances"][0]["rows"].append([id_, "OPHOURS", 100000.0, None])
    for name in ("System", "Item"):
        t = table(tables, name)
        columns = [c["name"] for c in t["columns"]]
        row = t["instances"][0]["rows"][0]
        if row[columns.index("OPID")] != "OPHOURS" or row[columns.index("FRT")] != 300000:
            raise ValueError(f"base {name} FRT changed")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D07.var03 input differs")
    print(json.dumps({"variant_id": "D07.var03", "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
