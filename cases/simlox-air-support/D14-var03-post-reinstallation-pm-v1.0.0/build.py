"""Extend accepted D14 zero-age arms by one post-reinstallation sortie."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var02-03-zero-age-reinstallation-v1.0.0"
PARENT_SHA = {
    "monitored": "0345fe8ff1c7e86a3332f4ef822adf92814e6a0562bb30cbfa305b4a89a00b7c",
    "system-converted": "cd0bd500b3f7a5496fe730244e225484c79041ec33502a940e09c516ed4b3056",
}


def table(tables: list[dict], name: str) -> dict:
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected table topology: {name}")
    return matches[0]


def make(arm: str) -> dict:
    if arm not in PARENT_SHA:
        raise ValueError(arm)
    source = (PARENT / f"native-input-{arm}.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA[arm]:
        raise ValueError("accepted parent changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    desc = table(tables, "ProblemDescription")["instances"][0]["rows"]
    if len(desc) != 1:
        raise ValueError("unexpected description")
    desc[0][0] = f"D14.var03 PM after physical reinstallation MONIT={'Y' if arm == 'monitored' else 'N'}"
    profile = table(tables, "OperationProfile")["instances"][0]["rows"]
    if [row[2] for row in profile] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected accepted mission schedule")
    fourth = copy.deepcopy(profile[-1])
    fourth[2] = 44.0
    profile.append(fourth)
    control = table(tables, "Control")["instances"][0]["rows"]
    if len(control) != 1 or control[0][1] != 36.0 or control[0][6] != 36.0:
        raise ValueError("unexpected accepted horizon")
    control[0][1] = control[0][6] = 48.0
    collection = table(tables, "ResultCollection")["instances"][0]["rows"]
    if len(collection) != 2 or any(row[3] != 36.0 for row in collection):
        raise ValueError("unexpected accepted result windows")
    for row in collection:
        row[3] = 48.0
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    result = {}
    for arm in PARENT_SHA:
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen {arm} differs")
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "D14", "variant_id": "D14.var03",
                      "parent_sha256": PARENT_SHA, "inputs": result}))


if __name__ == "__main__":
    main()
