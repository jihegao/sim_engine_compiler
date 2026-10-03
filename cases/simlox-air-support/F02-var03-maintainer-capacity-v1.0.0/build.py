"""Derive F02.var03 two-maintainer arm from the accepted F02 risk fleet."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "F02-var01-var02-integrated-fleet-v1.0.2"
PARENT_INPUT = PARENT / "risk-input.json"
PARENT_SHA = "ae46b08a6ef6fd063906b888fb3c73fba06edcb57acc1a4ade49fc62c53fd7d3"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if sha(PARENT_INPUT) != PARENT_SHA:
        raise ValueError("accepted F02 risk input changed")
    doc = copy.deepcopy(json.loads(PARENT_INPUT.read_bytes()))
    allocation = next(t for t in doc["model"]["tables"] if t["name"] == "ResourceAllocation")
    fields = [c["name"] for c in allocation["columns"]]
    rows = allocation["instances"][0]["rows"]
    maint = [r for r in rows if r[fields.index("RID")] == "P-MAINT"]
    if len(maint) != 1 or maint[0][fields.index("RQTY")] != 1:
        raise ValueError("unexpected P-MAINT parent allocation")
    maint[0][fields.index("RQTY")] = 2
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "no-conflict-input.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen no-conflict input changed")
    print(json.dumps({"input_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
