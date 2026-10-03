"""Recompute source deltas for the two factorized usage arms."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import ARMS, DIRECT_HALF, DIRECT_HALF_SHA, HERE, PARENT, PARENT_SHA, make


def mapped(doc: dict) -> dict:
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")
    return tables


def delta(a: dict, b: dict) -> dict:
    return {n: {"before": a.get(n), "after": b.get(n)} for n in b if a.get(n) != b.get(n)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent, half = (mapped(json.loads(p.read_bytes())) for p in (PARENT, DIRECT_HALF))
    arms = {arm: mapped(make(arm)) for arm in ARMS}
    from_parent = {arm: delta(parent, arms[arm]) for arm in ARMS}
    from_half = delta(half, arms["factorhalf"])
    between = delta(arms["factorhalf"], arms["factorfull"])
    if any(set(d) != {"ProblemDescription", "MaterielOperationalModes"} for d in
           (*from_parent.values(), from_half, between)):
        raise ValueError("unexpected business table delta")
    result = {"schema": "simlox-air-support-exact-usert-product-diff/v1", "case_id": "G09",
              "variant_id": "G09.var05", "parent_sha256": PARENT_SHA,
              "direct_half_sha256": DIRECT_HALF_SHA,
              "input_sha256": {a: hashlib.sha256((HERE / f"{a}-input.json").read_bytes()).hexdigest() for a in ARMS},
              "from_parent": from_parent, "from_direct_half": from_half, "between_arms": between}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff changed")
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
