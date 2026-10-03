"""Derive a 52-hour slow-route terminal probe from the accepted F02 risk input."""
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
OUTPUT = HERE / "terminal-input.json"
HORIZON = 52.0
TRANSIT = 5.0


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
    for field in ("SIMPE", "RCEND"):
        rows[0][fields.index(field)] = HORIZON
    route = tables["StationStructure"]
    fields = [column["name"] for column in route["columns"]]
    rows = [row for instance in route["instances"] for row in instance["rows"]]
    if len(rows) != 1 or rows[0][fields.index("STID")] != "BASE-01" or rows[0][fields.index("MSTID")] != "DEPOT-01":
        raise ValueError("unexpected parent base/depot route")
    for field in ("TFRMS", "TTOMS"):
        if rows[0][fields.index(field)] != 2.0:
            raise ValueError("unexpected parent route duration")
        rows[0][fields.index(field)] = TRANSIT
    collection = tables["ResultCollection"]
    fields = [column["name"] for column in collection["columns"]]
    rows = [row for instance in collection["instances"] for row in instance["rows"]]
    if not rows or any(row[fields.index("RCEND")] != 60.0 for row in rows):
        raise ValueError("unexpected parent ResultCollection horizon")
    for row in rows:
        row[fields.index("RCEND")] = HORIZON
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
