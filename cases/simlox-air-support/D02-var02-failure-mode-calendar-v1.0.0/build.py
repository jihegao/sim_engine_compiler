"""Derive a CALHOURS failure-mode clock from accepted D06 OPHOURS control."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
OUTPUT = HERE / "native-input.json"


def row(tables: list[dict], name: str) -> tuple[list[str], list]:
    t = next(x for x in tables if x["name"] == name)
    names = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or len(rows[0]) != len(names):
        raise ValueError(f"unexpected {name} shape")
    return names, rows[0]


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D06 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    names, values = row(tables, "ProblemDescription")
    values[names.index("PDESC")] = "D02.var02 explicit position-A failure mode on CALHOURS clock"
    names, values = row(tables, "FailureMode")
    if values[names.index("FMID")] != "FM-POS-A" or values[names.index("OPID")] != "OPHOURS":
        raise ValueError("unexpected accepted D06 failure mode")
    values[names.index("OPID")] = "CALHOURS"
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
        raise ValueError("frozen D02.var02 input differs")
    print(json.dumps({"case_id": "D02", "variant_id": "D02.var02",
                      "parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
