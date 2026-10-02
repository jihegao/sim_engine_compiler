"""Build an isolated seeded RANDOM versus EQUIDIST system-prelife pair."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var02-equidist-system-prelife-v1.0.1" / "native-input-equidist.json"
PARENT_SHA = "fe5ef789385330d275709b2e0a124bfde2268ca51e1236692ff36cd92e3d3ece"
ARMS = ("equidist-control", "random-seed1")


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var02 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    table(tables, "ProblemDescription")["instances"][0]["rows"][0][0] = "G11.var03 one-seed system RANDOM prelife; " + arm
    profile = table(tables, "OperationProfile")
    profile_rows = profile["instances"][0]["rows"]
    if len(profile_rows) != 3:
        raise ValueError("accepted mission rows differ")
    profile_names = [c["name"] for c in profile["columns"]]
    if [r[profile_names.index("STIM")] for r in profile_rows] != [8.0, 12.0, 32.0]:
        raise ValueError("accepted mission starts differ")
    for row in profile_rows:
        row[profile_names.index("IQTY")] = 0
    prelife = table(tables, "PrelifeData")
    rows = prelife["instances"][0]["rows"]
    if len(rows) != 1 or rows[0][:7] != ["PL-SYS", "EQ-0-120", 3, 120.0, 0.0, "CALHOURS", "EQUIDIST"]:
        raise ValueError("accepted EQUIDIST row differs")
    if arm == "random-seed1":
        rows[0][1] = "RND-0-120"
        rows[0][6] = "RANDOM"
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    shas = {}
    for arm in ARMS:
        raw = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        elif path.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var03", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
