"""Recompute exact accepted tree-to-mode-arm table deltas."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent = mapped(json.loads(PARENT.read_bytes()))
    arms = {}
    expected = {"ProblemDescription", "OperationalModes", "MaterielOperationalModes", "RBDTreeStructure"}
    for arm in ARMS:
        child = mapped(make(arm))
        changed = {n: {"before": parent[n], "after": child[n]} for n in parent if parent[n] != child[n]}
        if set(changed) != expected:
            raise ValueError(f"unexpected {arm} tables: {sorted(changed)}")
        arms[arm] = {"input_sha256": hashlib.sha256((HERE / f"{arm}-input.json").read_bytes()).hexdigest(),
                     "changed": changed}
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G08",
              "variant_id": "G08.var05", "parent_sha256": PARENT_SHA, "arms": arms}
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
