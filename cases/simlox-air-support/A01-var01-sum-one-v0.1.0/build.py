"""Build one TFOUT=0.75 child from the accepted frozen A01 JSON input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
PARENT_SHA = "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7"
OUTPUT = HERE / "native-input.json"

def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A01 input SHA differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = [table for table in doc["model"]["tables"] if table["name"] == "MissionType"]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError("unexpected MissionType table shape")
    table = tables[0]
    columns = [column["name"] for column in table["columns"]]
    rows = table["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(columns):
        raise ValueError("unexpected MissionType row shape")
    row = rows[0]
    for name, expected in (("MTID", "BASIC-MISSION"), ("DURN", 2.0),
                           ("TFOUT", 0.25), ("TFRET", 0.25)):
        if row[columns.index(name)] != expected:
            raise ValueError(f"accepted A01 {name} differs")
    row[columns.index("TFOUT")] = 0.75
    return doc

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(data)
    elif OUTPUT.read_bytes() != data:
        raise ValueError("frozen A01.var01 source differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "only_change": "MissionType.TFOUT 0.25 to 0.75"}))

if __name__ == "__main__":
    main()
