"""Freeze and replay the exact D02.var03 long-parking parent delta."""
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
        raise ValueError("accepted parent fingerprint differs")
    parent = {t["name"]: t for t in json.loads(parent_raw)["model"]["tables"]}
    child = {t["name"]: t for t in json.loads(child_raw)["model"]["tables"]}
    changed = {n: {"parent": parent[n], "child": child[n]}
               for n in parent if parent[n] != child.get(n)}
    expected = {"ProblemDescription", "Control", "OperationProfile", "ResultCollection"}
    if set(parent) != set(child) or set(changed) != expected:
        raise ValueError("unexpected parent table delta")
    profile = changed["OperationProfile"]
    before = profile["parent"]["instances"][0]["rows"]
    after = profile["child"]["instances"][0]["rows"]
    columns = [c["name"] for c in profile["parent"]["columns"]]
    index = columns.index("STIM")
    if len(before) != 3 or len(after) != 3 or any(
        b[:index] != a[:index] or b[index + 1:] != a[index + 1:]
        for b, a in zip(before, after, strict=True)
    ) or [r[index] for r in before] != [8, 20, 52] or [r[index] for r in after] != [8, 20, 152]:
        raise ValueError("unexpected profile delta")
    result = {"schema": "simlox-d02-var03-long-parking-exact-parent-diff/v1",
              "case_id": "D02", "variant_id": "D02.var03", "version": "1.0.0-candidate",
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
