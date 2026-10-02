"""Freeze explicit versus wildcard top-level Prelife.MID from G11.var07."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G11-var07-age-cycle-boundary-v1.0.0" / "native-input-equal-boundary.json"
PARENT_SHA = "8a4aba63adda8a10c0eb9c731c52be5fc1b47b35c3c605f9bafe073f13097d2f"
ARMS = ("explicit-mid", "wildcard-mid")


def table(doc: dict, name: str) -> dict:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table")
    return matches[0]


def make(arm: str) -> dict:
    if arm not in ARMS:
        raise ValueError(arm)
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("accepted G11.var07 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "G11.var08 top-level Prelife.MID wildcard; " + arm)
    prelife = table(doc, "Prelife")
    rows = prelife["instances"][0]["rows"]
    columns = [c["name"] for c in prelife["columns"]]
    if len(rows) != 1 or rows[0][columns.index("PLID")] != "PL-SYS" or rows[0][columns.index("MID")] != "TEACH-AIR-01":
        raise ValueError("accepted top-level Prelife row differs")
    rows[0][columns.index("MID")] = "TEACH-AIR-01" if arm == "explicit-mid" else "*"
    deployment = table(doc, "SystemDeployment")
    dcols = [c["name"] for c in deployment["columns"]]
    drows = deployment["instances"][0]["rows"]
    if len(drows) != 1 or drows[0][dcols.index("QTYPS")] != 3 or drows[0][dcols.index("PLID")] != "PL-SYS":
        raise ValueError("accepted deployment differs")
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
    print(json.dumps({"case_id": "G11", "variant_id": "G11.var08", "parent_sha256": PARENT_SHA, "inputs": shas}))


if __name__ == "__main__":
    main()
