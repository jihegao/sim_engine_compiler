"""Recompute exact accepted G04 parent-to-tree-arm table deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import ARMS, HERE, PARENT, PARENT_SHA, make


def table_map(doc: dict) -> dict:
    found = {t["name"]: t for t in doc["model"]["tables"]}
    if len(found) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent = table_map(json.loads(PARENT.read_bytes()))
    arms = {}
    expected = {"ProblemDescription", "MaterielPosition", "MaterielStructure", "MaterielOperationalModes",
                "RBDParallel", "RBDParallelStructure", "RBDTree", "RBDTreeStructure"}
    for arm in ARMS:
        child = table_map(make(arm))
        changed = {name: {"before": parent.get(name), "after": child.get(name)}
                   for name in sorted(set(parent) | set(child)) if parent.get(name) != child.get(name)}
        if set(changed) != expected:
            raise ValueError(f"unexpected {arm} tables: {sorted(changed)}")
        arms[arm] = {"input_sha256": hashlib.sha256((HERE / f"{arm}-input.json").read_bytes()).hexdigest(),
                     "changed": changed}
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G08",
              "variant_ids": ["G08.var01", "G08.var02"], "parent_sha256": PARENT_SHA, "arms": arms}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(),
                      "changed_tables": {arm: sorted(data["changed"]) for arm, data in arms.items()}}))


if __name__ == "__main__":
    main()
