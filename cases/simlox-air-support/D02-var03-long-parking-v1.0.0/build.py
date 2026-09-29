"""Derive a 130-hour no-flight interval from accepted D02.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json"
PARENT_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"
CHILD = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    return matches[0]


def set_one(doc: dict, table_name: str, field: str, expected: object, value: object) -> None:
    t = table(doc, table_name)
    names = [c["name"] for c in t["columns"]]
    values = t["instances"][0]["rows"]
    if len(values) != 1 or field not in names or values[0][names.index(field)] != expected:
        raise ValueError(f"unexpected {table_name}.{field}")
    values[0][names.index(field)] = value


def build(parent_raw: bytes) -> dict:
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted D02.var01 parent fingerprint differs")
    child = copy.deepcopy(json.loads(parent_raw))
    set_one(child, "ProblemDescription", "PDESC",
            "D02.var01 traditional LRU OPHOURS across 30-hour no-flight gap",
            "D02.var03 traditional LRU OPHOURS across 130-hour no-flight gap")
    set_one(child, "Control", "SIMPE", 60, 160.0)
    set_one(child, "Control", "RCEND", 60, 160.0)
    result = table(child, "ResultCollection")
    names = [c["name"] for c in result["columns"]]
    values = result["instances"][0]["rows"]
    if len(values) != 2 or [r[names.index("RCEND")] for r in values] != [60, 60]:
        raise ValueError("unexpected parent result collection horizon")
    for row in values:
        row[names.index("RCEND")] = 160.0
    profile = table(child, "OperationProfile")
    names = [c["name"] for c in profile["columns"]]
    values = profile["instances"][0]["rows"]
    if len(values) != 3 or [r[names.index("STIM")] for r in values] != [8, 20, 52]:
        raise ValueError("unexpected parent profile")
    values[2][names.index("STIM")] = 152.0
    return child


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    child = build(PARENT.read_bytes())
    raw = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if CHILD.exists():
            raise FileExistsError(CHILD)
        CHILD.write_bytes(raw)
    elif CHILD.read_bytes() != raw:
        raise ValueError("frozen child input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA,
                      "child_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
