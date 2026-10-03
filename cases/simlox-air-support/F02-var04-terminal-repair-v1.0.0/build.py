"""Derive a 60-hour active-removal terminal probe from accepted F02 risk input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F02-var01-var02-integrated-fleet-v1.0.2"
PARENT_INPUT = PARENT / "risk-input.json"
PARENT_SHA = "ae46b08a6ef6fd063906b888fb3c73fba06edcb57acc1a4ade49fc62c53fd7d3"
OUTPUT = HERE / "repair-input.json"
HORIZON = 60.0
REMOVAL = 15.0
TOTAL_SURP = REMOVAL + 1 / 3


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted F02 parent input changed")
    doc = copy.deepcopy(json.loads(PARENT_INPUT.read_bytes()))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    control = tables["Control"]
    fields = [column["name"] for column in control["columns"]]
    rows = [row for instance in control["instances"] for row in instance["rows"]]
    if len(rows) != 1 or rows[0][fields.index("SIMPE")] != 60.0 or rows[0][fields.index("RCEND")] != 60.0:
        raise ValueError("unexpected parent Control horizon")
    repair = tables["SystemRepair"]
    fields = [column["name"] for column in repair["columns"]]
    rows = [row for instance in repair["instances"] for row in instance["rows"]]
    if len(rows) != 1 or rows[0][fields.index("SID")] != "TEACH-AIR-01" or rows[0][fields.index("STID")] != "BASE-01" or rows[0][fields.index("SURPTID")] != "E01-SURP" or rows[0][fields.index("SURPT")] != 0.5:
        raise ValueError("unexpected parent system replacement task")
    rows[0][fields.index("SURPT")] = TOTAL_SURP
    breakdown = tables["TaskBreakDown"]
    fields = [column["name"] for column in breakdown["columns"]]
    rows = [row for instance in breakdown["instances"] for row in instance["rows"]]
    removal = [row for row in rows if row[fields.index("TID")] == "E01-SURP" and row[fields.index("SEQ")] == 1 and row[fields.index("SUTID")] == "<REMOVE>"]
    if len(removal) != 1 or removal[0][fields.index("DURN")] != 1 / 6:
        raise ValueError("unexpected parent LRU removal duration")
    removal[0][fields.index("DURN")] = REMOVAL
    collection = tables["ResultCollection"]
    fields = [column["name"] for column in collection["columns"]]
    rows = [row for instance in collection["instances"] for row in instance["rows"]]
    if not rows or any(row[fields.index("RCEND")] != HORIZON for row in rows):
        raise ValueError("unexpected parent ResultCollection horizon")
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
        raise ValueError("frozen terminal input changed")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
