"""Derive MAXPM=2 control from the frozen D13.var02 MAXPM=1 case."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D13-var02-maxpm-one-v1.0.0" / "native-input.json"
PARENT_SHA256 = "8881ab42a492ce066dd23a51830b039768c316282e241fd45ee73d0ed5ee9748"
OUTPUT = HERE / "native-input.json"


def one(model: dict, name: str, **values: object) -> None:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    t = found[0]
    fields = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or set(values) - set(fields):
        raise ValueError(f"unexpected {name} rows")
    for field, value in values.items():
        rows[0][fields.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("MAXPM one parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    one(model, "ProblemDescription", PDESC="D13.var02 two calendar-PM aircraft, MAXPM two")
    one(model, "Unit", MAXPM=2)
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
        raise ValueError("frozen D13 MAXPM two input differs from builder")
    print(json.dumps({"case_id": "D13.var02", "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "parent_sha256": PARENT_SHA256, "bytes": len(raw)}))


if __name__ == "__main__":
    main()
