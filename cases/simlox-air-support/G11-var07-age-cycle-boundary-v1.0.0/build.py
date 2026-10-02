"""Freeze fixed CAL100 prelife ages below, equal to and above one cycle."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var01-fixed-system-prelife-v1.0.0" / "native-input-fixed-ages.json"
PARENT_SHA = "a8836588aa09973b78195cf515cdc1ed4916c4f1653690e3bbd38fd0a5fb4bd2"
ARMS = ("above-control", "equal-boundary")


def table(tables: list[dict], name: str) -> dict:
    matches = [t for t in tables if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    table(tables, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "G11.var07 CAL100 initial age strict cycle boundary; " + arm)
    deployment = table(tables, "SystemDeployment")
    dcols = [c["name"] for c in deployment["columns"]]
    drows = deployment["instances"][0]["rows"]
    if len(drows) != 1 or drows[0][dcols.index("QTYPS")] != 3:
        raise ValueError("accepted deployment differs")
    profile = table(tables, "OperationProfile")
    pcols = [c["name"] for c in profile["columns"]]
    prows = profile["instances"][0]["rows"]
    if len(prows) != 3 or [r[pcols.index("STIM")] for r in prows] != [8.0, 20.0, 32.0]:
        raise ValueError("accepted mission schedule differs")
    for row in prows:
        row[pcols.index("IQTY")] = 0
    pdata = table(tables, "PrelifeData")
    rows = pdata["instances"][0]["rows"]
    expected = [
        ["PL-SYS", "AGE0", 1, 0.0, 0.0, "CALHOURS", "FIXED", None],
        ["PL-SYS", "AGE60", 1, 60.0, 0.0, "CALHOURS", "FIXED", None],
        ["PL-SYS", "AGE120", 1, 120.0, 0.0, "CALHOURS", "FIXED", None],
    ]
    if rows != expected:
        raise ValueError("accepted prelife rows differ")
    for row, label in zip(rows, ("BELOW", "MIDDLE", "ABOVE")):
        row[1] = label
    rows[0][3] = 60.0
    rows[1][3] = 120.0 if arm == "above-control" else 100.0
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    shas = {}
    for arm in ARMS:
        encoded = (json.dumps(make(arm), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"native-input-{arm}.json"
        if args.write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(encoded)
        elif path.read_bytes() != encoded:
            raise ValueError(f"frozen input differs: {arm}")
        shas[arm] = hashlib.sha256(encoded).hexdigest()
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var07", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
