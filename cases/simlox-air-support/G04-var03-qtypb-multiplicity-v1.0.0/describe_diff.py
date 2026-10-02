"""Recompute the exact G04.var03 table delta from the accepted parent."""
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
    parent, child = table_map(json.loads(PARENT.read_bytes())), table_map(make())
    if set(parent) != set(child):
        raise ValueError("table set differs")
    changed = {name: {"before": parent[name], "after": child[name]} for name in parent if parent[name] != child[name]}
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G04", "variant_id": "G04.var03",
              "parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256((HERE / "native-input.json").read_bytes()).hexdigest(),
              "changed": changed}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"changed_tables": list(changed), "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
