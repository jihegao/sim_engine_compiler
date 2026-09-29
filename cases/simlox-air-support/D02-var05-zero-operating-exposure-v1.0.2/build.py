"""Derive a zero-initiation OPHOURS control from accepted D02.var01."""
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


def build(parent_raw: bytes) -> dict:
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent fingerprint differs")
    child = copy.deepcopy(json.loads(parent_raw))
    table(child, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "D02.var05 zero operating exposure: scheduled profile with zero initiation quantities")
    profile = table(child, "OperationProfile")
    names = [c["name"] for c in profile["columns"]]
    records = profile["instances"][0]["rows"]
    if len(records) != 3 or [r[names.index("IQTY")] for r in records] != [1, 1, 1]:
        raise ValueError("unexpected parent initiation quantities")
    for row in records:
        row[names.index("IQTY")] = 0
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
