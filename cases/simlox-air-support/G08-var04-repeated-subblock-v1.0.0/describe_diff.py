"""Recompute exact accepted NBREQ3 parent-to-repeated-C table delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, make


def mapped(doc: dict) -> dict:
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")
    return tables


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before, after = (mapped(d) for d in (json.loads(PARENT.read_bytes()), make()))
    changed = {n: {"before": before[n], "after": after[n]} for n in before if before[n] != after[n]}
    if set(changed) != {"ProblemDescription", "MaterielStructure", "RBDTreeStructure"}:
        raise ValueError(f"unexpected tables: {sorted(changed)}")
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G08",
              "variant_id": "G08.var04", "parent_sha256": PARENT_SHA,
              "input_sha256": hashlib.sha256((HERE / "repeated-input.json").read_bytes()).hexdigest(),
              "changed": changed}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
