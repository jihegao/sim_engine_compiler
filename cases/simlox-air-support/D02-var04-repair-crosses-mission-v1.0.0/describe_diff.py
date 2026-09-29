"""Freeze and replay the D02.var04 exact D06 parent-table delta."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build import PARENT, PARENT_SHA, CHILD, HERE

OUT = HERE / "parent-diff.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw, child_raw = PARENT.read_bytes(), CHILD.read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError("accepted D06 parent fingerprint differs")
    parent = {t["name"]: t for t in json.loads(parent_raw)["model"]["tables"]}
    child = {t["name"]: t for t in json.loads(child_raw)["model"]["tables"]}
    changed = {n: {"parent": parent[n], "child": child[n]}
               for n in parent if parent[n] != child.get(n)}
    if set(parent) != set(child) or set(changed) != {"ProblemDescription", "CMLocation"}:
        raise ValueError("unexpected parent table delta")
    cm = changed["CMLocation"]
    before = cm["parent"]["instances"][0]["rows"]
    after = cm["child"]["instances"][0]["rows"]
    names = [c["name"] for c in cm["parent"]["columns"]]
    index = names.index("CMT")
    if len(before) != 1 or len(after) != 1 or before[0][:index] != after[0][:index] \
            or before[0][index + 1:] != after[0][index + 1:] \
            or (before[0][index], after[0][index]) != (0.5, 15.5):
        raise ValueError("unexpected CMLocation field delta")
    result = {"schema": "simlox-d02-var04-cross-mission-exact-parent-diff/v1",
              "case_id": "D02", "variant_id": "D02.var04", "version": "1.0.0-candidate",
              "parent_input_sha256": PARENT_SHA, "child_input_sha256": sha(child_raw),
              "changed_tables_only": list(changed), "added_tables_only": [],
              "unchanged_table_count": len(parent) - len(changed),
              "changed_tables": changed, "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen parent diff differs")
    print(json.dumps({"changed_tables_only": list(changed),
                      "unchanged_table_count": result["unchanged_table_count"],
                      "diff_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
