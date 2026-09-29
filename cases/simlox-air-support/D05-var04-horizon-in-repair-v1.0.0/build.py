"""Derive D05.var04's hour-26 repair-in-progress boundary from accepted D05."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0" / "native-input.json"
PARENT_SHA256 = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
OUTPUT = HERE / "native-input.json"


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1:
        raise ValueError(f"unexpected {name} table count")
    return found[0]


def set_one(model: dict, name: str, **values: object) -> None:
    item = table(model, name)
    if len(item["instances"]) != 1 or len(item["instances"][0]["rows"]) != 1:
        raise ValueError(f"unexpected {name} row shape")
    columns = [c["name"] for c in item["columns"]]
    if set(values) - set(columns):
        raise ValueError(f"unexpected {name} columns")
    row = item["instances"][0]["rows"][0]
    for field, value in values.items():
        row[columns.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D05 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    set_one(model, "ProblemDescription", PDESC="D05.var04 horizon during direct repair")
    set_one(model, "Control", SIMPE=26.0, RCEND=26.0)
    profile = table(model, "OperationProfile")
    profile_columns = [c["name"] for c in profile["columns"]]
    start_index = profile_columns.index("STIM")
    profile_rows = profile["instances"][0]["rows"]
    if len(profile_rows) != 3 or [row[start_index] for row in profile_rows] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected parent mission schedule")
    profile["instances"][0]["rows"] = profile_rows[:2]
    result = table(model, "ResultCollection")
    columns = [c["name"] for c in result["columns"]]
    index = columns.index("RCEND")
    for instance in result["instances"]:
        for row in instance["rows"]:
            row[index] = 26.0
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
        raise ValueError("frozen D05.var04 input differs")
    print(json.dumps({"case_id": "D05", "variant_id": "D05.var04",
                      "parent_sha256": PARENT_SHA256,
                      "input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
