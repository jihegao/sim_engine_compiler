"""Freeze a child-KM-rate-exceeds-mother diagnostic from accepted D07.var02."""
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
        "D07.var04 child KM rate exceeds mother system KM rate"
    )
    child = table(tables, "ItemFailureRate")
    system = table(tables, "SystemFailureRate")
    if child["instances"][0]["rows"] != [["TEACH-LRU-01", "KM", 5000.0, None]]:
        raise ValueError("accepted item KM rate differs")
    if system["instances"][0]["rows"] != [["TEACH-AIR-01", "KM", 5000.0, None]]:
        raise ValueError("accepted system KM rate differs")
    child["instances"][0]["rows"][0][2] = 10000.0
    item_structure = table(tables, "ItemStructure")
    columns = [c["name"] for c in item_structure["columns"]]
    rows = item_structure["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][columns.index("IID")] != "TEACH-LRU-01" or rows[0][columns.index("MID")] != "TEACH-AIR-01" or rows[0][columns.index("QTYPM")] != 1:
        raise ValueError("expected single installed child relation differs")
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
        raise ValueError("frozen D07.var04 input differs")
    print(json.dumps({"variant_id": "D07.var04", "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
