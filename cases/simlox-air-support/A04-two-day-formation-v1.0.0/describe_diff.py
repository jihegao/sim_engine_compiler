"""Freeze and replay A04's exact A03 parent table delta."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build import PARENT, PARENT_SHA, PROFILE_SHA, CHILD, HERE, sha, build

OUT = HERE / "parent-diff.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw, child_raw = PARENT.read_bytes(), CHILD.read_bytes()
    if sha(parent_raw) != PARENT_SHA or json.loads(child_raw) != build():
        raise ValueError("frozen sources or A04 builder differ")
    parent = {t["name"]: t for t in json.loads(parent_raw)["model"]["tables"]}
    child = {t["name"]: t for t in json.loads(child_raw)["model"]["tables"]}
    changed = {n: {"parent": parent[n], "child": child[n]}
               for n in parent if parent[n] != child.get(n)}
    expected = {"ProblemDescription", "Unit", "Control", "OperationProfile", "ResultCollection"}
    if set(parent) != set(child) or set(changed) != expected:
        raise ValueError("unexpected A03 parent table delta")
    result = {"schema": "simlox-a04-two-day-formation-exact-parent-diff/v1",
              "case_id": "A04", "version": "1.0.0-candidate",
              "parent_input_sha256": PARENT_SHA, "profile_source_sha256": PROFILE_SHA,
              "child_input_sha256": sha(child_raw), "changed_tables_only": list(changed),
              "added_tables_only": [], "unchanged_table_count": len(parent) - len(changed),
              "changed_tables": changed, "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen A04 parent diff differs")
    print(json.dumps({"changed_tables_only": list(changed),
                      "unchanged_table_count": result["unchanged_table_count"],
                      "diff_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
