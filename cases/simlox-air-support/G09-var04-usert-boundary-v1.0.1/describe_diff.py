"""Recompute exact parent and pairwise USERT table deltas."""
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
    arms = {a: mapped(make(a)) for a in ARMS}
    from_parent = {a: delta(parent, arms[a]) for a in ARMS}
    between = {a: delta(arms["use1"], arms[a]) for a in ARMS if a != "use1"}
    expected = {"ProblemDescription", "FailureMode", "OperationalModes", "MaterielOperationalModes", "RBDSeriesStructure"}
    if any(set(v) != expected for v in from_parent.values()):
        raise ValueError("unexpected parent delta")
    if any(set(v) != {"ProblemDescription", "MaterielOperationalModes"} for v in between.values()):
        raise ValueError("unexpected between-arm delta")
    result = {"schema": "simlox-air-support-exact-usert-panel-diff/v1", "case_id": "G09",
              "variant_id": "G09.var04", "parent_sha256": PARENT_SHA,
              "input_sha256": {a: hashlib.sha256((HERE / f"{a}-input.json").read_bytes()).hexdigest() for a in ARMS},
              "from_parent": from_parent, "from_use1": between}
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
