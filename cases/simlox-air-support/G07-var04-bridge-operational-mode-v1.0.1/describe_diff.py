"""Recompute the exact accepted-parent to bridge-mode table delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, make


def table_map(doc: dict) -> dict:
    result = {t["name"]: t for t in doc["model"]["tables"]}
    if len(result) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent = table_map(json.loads(PARENT.read_bytes()))
    child = table_map(make())
    if set(parent) != set(child):
        raise ValueError("table set changed")
    changed = {name: {"before": parent[name], "after": child[name]}
               for name in parent if parent[name] != child[name]}
    if set(changed) != {"ProblemDescription", "OperationalModes", "MaterielOperationalModes", "RBDBridge"}:
        raise ValueError(f"unexpected changed tables: {sorted(changed)}")
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G07",
              "variant_id": "G07.var04", "parent_sha256": PARENT_SHA,
              "arm": "br75", "input_sha256": hashlib.sha256((HERE / "br75-input.json").read_bytes()).hexdigest(),
              "changed": changed}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_tables": sorted(changed)}))


if __name__ == "__main__":
    main()
