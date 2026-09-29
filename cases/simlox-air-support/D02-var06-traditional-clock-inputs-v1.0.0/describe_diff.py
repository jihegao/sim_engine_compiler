"""Freeze and replay exact D02.var06 parent-table differences."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, VARIANTS

OUT = HERE / "parent-diffs.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError("accepted parent SHA differs")
    parent = {t["name"]: t for t in json.loads(parent_raw)["model"]["tables"]}
    variants = {}
    for variant in VARIANTS:
        child_raw = (HERE / f"native-input-{variant}.json").read_bytes()
        child = {t["name"]: t for t in json.loads(child_raw)["model"]["tables"]}
        changed = {n: {"parent": parent[n], "child": child[n]}
                   for n in parent if n in child and parent[n] != child[n]}
        added = {n: child[n] for n in child.keys() - parent.keys()}
        deleted = set(parent) - set(child)
        expected = {"ProblemDescription", "Item"} if variant.startswith("item-") \
            else {"ProblemDescription"}
        if set(changed) != expected or set(added) != (set() if variant.startswith("item-")
                                                     else {"ItemFailureRate"}) or deleted:
            raise ValueError(f"unexpected {variant} table delta")
        variants[variant] = {"child_input_sha256": sha(child_raw),
                             "changed_tables_only": sorted(changed),
                             "added_tables_only": sorted(added),
                             "unchanged_table_count": len(parent) - len(changed),
                             "changed_tables": changed, "added_tables": added}
    result = {"schema": "simlox-d02-var06-exact-parent-diffs/v1",
              "case_id": "D02", "variant_id": "D02.var06", "version": "1.0.0-candidate",
              "parent_input_sha256": PARENT_SHA, "variants": variants,
              "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen parent diffs differ")
    print(json.dumps({"diff_sha256": sha(raw),
                      "variants": {k: {"changed": v["changed_tables_only"],
                                       "added": v["added_tables_only"],
                                       "unchanged": v["unchanged_table_count"]}
                                   for k, v in variants.items()}}))


if __name__ == "__main__":
    main()
