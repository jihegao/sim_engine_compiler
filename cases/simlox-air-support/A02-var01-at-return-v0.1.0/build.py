"""Build the A02 at-return child from the accepted frozen A02 input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
OUTPUT = HERE / "native-input.json"

def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted A02 input SHA differs")
    doc = copy.deepcopy(json.loads(raw))
    matches = [table for table in doc["model"]["tables"] if table["name"] == "OperationProfile"]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError("unexpected OperationProfile table shape")
    table = matches[0]
    columns = [column["name"] for column in table["columns"]]
    rows = table["instances"][0]["rows"]
    if len(rows) != 3 or any(len(row) != len(columns) for row in rows):
        raise ValueError("unexpected OperationProfile row shape")
    for row, start in zip(rows, (8.0, 20.0, 32.0)):
        for name, expected in (("PRID", "BASIC-SCHEDULE"), ("SPRID", "BASIC-MISSION"),
                               ("STIM", start), ("DTIM", 1/3)):
            if row[columns.index(name)] != expected:
                raise ValueError(f"accepted A02 {name} differs at STIM {start}")
    rows[1][columns.index("STIM")] = 10.0
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
        raise ValueError("frozen A02.var01 source differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(data).hexdigest(),
                      "bytes": len(data), "only_change": "OperationProfile second STIM 20 to 10"}))

if __name__ == "__main__":
    main()
