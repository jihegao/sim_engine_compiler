"""Build the one-cell OPHOURS=4 threshold child from accepted D04 bytes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D04-flight-hour-pm-v1.0.0" / "native-input.json"
PARENT_SHA = "d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a"
OUTPUT = HERE / "native-input.json"


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D04 input fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = [t for t in doc["model"]["tables"] if t["name"] == "MaterielPM"]
    if len(tables) != 1 or len(tables[0]["instances"]) != 1:
        raise ValueError("unexpected MaterielPM table/instance shape")
    table = tables[0]
    columns = [item["name"] for item in table["columns"]]
    rows = table["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(columns):
        raise ValueError("unexpected MaterielPM row shape")
    row = rows[0]
    for field, expected in (("PMID", "OP3"), ("PMINT", 3.0), ("OPID", "OPHOURS"),
                            ("ATIM", 0.0), ("DTIM", 0.0)):
        if row[columns.index(field)] != expected:
            raise ValueError(f"accepted D04 {field} differs")
    row[columns.index("PMINT")] = 4.0
    return doc


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D04.var01 input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": len(raw), "only_change": "MaterielPM.PMINT 3 to 4 OPHOURS"}))


if __name__ == "__main__":
    main()
