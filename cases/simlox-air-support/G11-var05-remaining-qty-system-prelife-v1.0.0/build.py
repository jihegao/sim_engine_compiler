"""Freeze four-system explicit-QTY versus blank-remaining prelife pair."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var01-fixed-system-prelife-v1.0.0" / "native-input-fixed-ages.json"
PARENT_SHA = "a8836588aa09973b78195cf515cdc1ed4916c4f1653690e3bbd38fd0a5fb4bd2"
ARMS = ("explicit-two", "remaining-blank")


def table(tables: list[dict], name: str) -> dict:
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def field(table_obj: dict, row: list, name: str, value) -> None:
    columns = [c["name"] for c in table_obj["columns"]]
    row[columns.index(name)] = value


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    parent_raw = PARENT.read_bytes()
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var01 parent changed")
    doc = copy.deepcopy(json.loads(parent_raw))
    tables = doc["model"]["tables"]
    table(tables, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "G11.var05 four-system PrelifeData QTY remainder; " + arm)
    deployment = table(tables, "SystemDeployment")
    dr = deployment["instances"][0]["rows"]
    if len(dr) != 1:
        raise ValueError("accepted deployment rows differ")
    field(deployment, dr[0], "QTYPS", 4)
    profile = table(tables, "OperationProfile")
    pr = profile["instances"][0]["rows"]
    if len(pr) != 3 or [r[2] for r in pr] != [8.0, 20.0, 32.0]:
        raise ValueError("accepted mission schedule differs")
    for row in pr:
        field(profile, row, "IQTY", 0)
    prelife = table(tables, "PrelifeData")
    rows = prelife["instances"][0]["rows"]
    expected = [
        ["PL-SYS", "AGE0", 1, 0.0, 0.0, "CALHOURS", "FIXED", None],
        ["PL-SYS", "AGE60", 1, 60.0, 0.0, "CALHOURS", "FIXED", None],
        ["PL-SYS", "AGE120", 1, 120.0, 0.0, "CALHOURS", "FIXED", None],
    ]
    if rows != expected:
        raise ValueError("accepted fixed-age rows differ")
    field(prelife, rows[2], "QTY", 2 if arm == "explicit-two" else None)
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
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var05", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
