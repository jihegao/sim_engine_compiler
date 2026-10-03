"""Recompute two-copy QTYNC1 versus QTYNC2 BASIC h20 deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import ARMS, HERE, PARENT, PARENT_SHA, make


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
    parent = mapped(json.loads(PARENT.read_bytes()))
    arms = {arm: mapped(make(arm)) for arm in ARMS}
    from_parent = {arm: delta(parent, arms[arm]) for arm in ARMS}
    pair = delta(arms[ARMS[0]], arms[ARMS[1]])
    if set(from_parent["qty1"]) != {"ProblemDescription", "MaterielStructure", "OperationProfile"}:
        raise ValueError("qty1 parent delta changed")
    if set(from_parent["qty2"]) != {"ProblemDescription", "MaterielStructure", "OperationProfile",
                                     "RBDNonCriticalSetItems"}:
        raise ValueError("qty2 parent delta changed")
    if set(pair) != {"ProblemDescription", "RBDNonCriticalSetItems"}:
        raise ValueError("pair QTYNC delta changed")
    result = {"schema": "simlox-air-support-exact-paired-table-diff/v1", "case_id": "G09",
              "variant_id": "G09.var03", "parent_sha256": PARENT_SHA,
              "input_sha256": {arm: hashlib.sha256((HERE / f"{arm}-input.json").read_bytes()).hexdigest()
                               for arm in ARMS},
              "from_parent": from_parent, "between_arms": pair}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen paired diff differs")
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
