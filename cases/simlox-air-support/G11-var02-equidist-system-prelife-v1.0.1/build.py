"""Build matched explicit FIXED and EQUIDIST system-prelife arms from accepted G11.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var01-fixed-system-prelife-v1.0.0" / "native-input-fixed-ages.json"
PARENT_SHA = "a8836588aa09973b78195cf515cdc1ed4916c4f1653690e3bbd38fd0a5fb4bd2"
ARMS = ("fixed-explicit", "equidist")


def table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected table {name}")
    return found[0]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    source = PARENT.read_bytes()
    if hashlib.sha256(source).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var01 input changed")
    doc = copy.deepcopy(json.loads(source))
    tables = doc["model"]["tables"]
    profile = table(tables, "OperationProfile")
    profile_names = [c["name"] for c in profile["columns"]]
    profile_rows = profile["instances"][0]["rows"]
    stim = profile_names.index("STIM")
    if [r[stim] for r in profile_rows] != [8.0, 20.0, 32.0]:
        raise ValueError("parent mission starts differ")
    profile_rows[1][stim] = 12.0
    pd = table(tables, "ProblemDescription")
    pd["instances"][0]["rows"][0][0] = "G11.var02 collision-free EQUIDIST check; " + arm
    data = table(tables, "PrelifeData")
    names = [c["name"] for c in data["columns"]]
    if names != ["PLID", "PLIND", "QTY", "AGE", "AGEMIN", "OPID", "TYPE", "NOTE"]:
        raise ValueError("parent prelife schema differs")
    rows = data["instances"][0]["rows"]
    if len(rows) != 3 or [r[1] for r in rows] != ["AGE0", "AGE60", "AGE120"]:
        raise ValueError("parent prelife rows differ")
    if arm == "fixed-explicit":
        for row, label, age in zip(rows, ("AGE40", "AGE80", "AGE120"), (40.0, 80.0, 120.0)):
            row[1], row[3] = label, age
    else:
        data["instances"][0]["rows"] = [["PL-SYS", "EQ-0-120", 3, 120.0, 0.0, "CALHOURS", "EQUIDIST", None]]
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
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var02", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
