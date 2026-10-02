"""Derive a position-linked MONIT=Y boundary probe from accepted D14.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var01-monitored-item-pm-v1.0.1" / "native-input-monitored.json"
PARENT_SHA = "29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903"


def make() -> dict:
    source = PARENT.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA:
        raise ValueError("accepted parent input changed")
    doc = copy.deepcopy(json.loads(source))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate tables")
    desc = tables["ProblemDescription"]["instances"][0]["rows"]
    pm = tables["MaterielPM"]
    fields = [c["name"] for c in pm["columns"]]
    rows = pm["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][fields.index("MID")] != "TEACH-LRU-01" or rows[0][fields.index("MONIT")] != "Y":
        raise ValueError("unexpected accepted PM row")
    positions = tables["MaterielPosition"]["instances"][0]["rows"]
    if len(positions) != 1 or positions[0][0] != "POS-A":
        raise ValueError("unexpected accepted position")
    desc[0][0] = "D14.var04 position-linked MONIT Y converter boundary"
    rows[0][fields.index("MID")] = "POS-A"
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    raw = (json.dumps(make(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "native-input.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif output.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"case_id": "D14", "variant_id": "D14.var04", "parent_sha256": PARENT_SHA,
                      "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
