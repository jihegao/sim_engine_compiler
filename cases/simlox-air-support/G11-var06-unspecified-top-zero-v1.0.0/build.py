"""Freeze a four-system explicit zero versus unspecified remainder pair."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var05-remaining-qty-system-prelife-v1.0.0" / "native-input-explicit-two.json"
PARENT_SHA = "afd693a6609c2454b3ec71a1f663791b61a932831720070d164d371c6aff9be2"
ARMS = ("explicit-zero", "implicit-zero")


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
        raise ValueError("accepted G11.var05 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    table(tables, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "G11.var06 four-system unspecified top-level zero; " + arm)
    deployment = table(tables, "SystemDeployment")
    dcols = [c["name"] for c in deployment["columns"]]
    drows = deployment["instances"][0]["rows"]
    if len(drows) != 1 or drows[0][dcols.index("QTYPS")] != 4:
        raise ValueError("accepted deployment differs")
    profile = table(tables, "OperationProfile")
    pcols = [c["name"] for c in profile["columns"]]
    prows = profile["instances"][0]["rows"]
    if len(prows) != 3 or [r[pcols.index("IQTY")] for r in prows] != [0, 0, 0]:
        raise ValueError("accepted zero-mission profile differs")
    prelife = table(tables, "PrelifeData")
    rows = prelife["instances"][0]["rows"]
    expected = [
        ["PL-SYS", "AGE0", 1, 0.0, 0.0, "CALHOURS", "FIXED", None],
        ["PL-SYS", "AGE60", 1, 60.0, 0.0, "CALHOURS", "FIXED", None],
        ["PL-SYS", "AGE120", 2, 120.0, 0.0, "CALHOURS", "FIXED", None],
    ]
    if rows != expected:
        raise ValueError("accepted fixed prelife rows differ")
    age60 = copy.deepcopy(rows[1])
    age0 = copy.deepcopy(rows[0])
    age0[2] = 3
    prelife["instances"][0]["rows"] = [age60, age0] if arm == "explicit-zero" else [age60]
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
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var06", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
