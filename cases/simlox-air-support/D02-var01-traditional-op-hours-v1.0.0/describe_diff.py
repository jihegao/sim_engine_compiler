"""Verify the D02.var01 long-gap delta from accepted D01 installed LRU."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "parent-diff.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
CHILD_SHA = "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw, child_raw = PARENT.read_bytes(), CHILD.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(child_raw) != CHILD_SHA:
        raise ValueError("source fingerprint differs")
    parent = {t["name"]: t for t in json.loads(parent_raw)["model"]["tables"]}
    child = {t["name"]: t for t in json.loads(child_raw)["model"]["tables"]}
    changed = {n: {"parent": parent[n], "child": child[n]}
               for n in parent if parent[n] != child.get(n)}
    if set(parent) != set(child) or set(changed) != {
        "ProblemDescription", "Control", "OperationProfile", "ResultCollection"
    }:
        raise ValueError("unexpected D02.var01 parent delta")
    result = {"schema": "simlox-d02-var01-traditional-op-exact-parent-diff/v1",
              "case_id": "D02", "variant_id": "D02.var01", "version": "1.0.0-candidate",
              "parent_input_sha256": PARENT_SHA, "child_input_sha256": CHILD_SHA,
              "changed_tables_only": list(changed), "added_tables_only": [],
              "unchanged_table_count": len(parent) - len(changed),
              "changed_tables": changed, "publication_state": "not_published"}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(encoded)
    elif OUT.read_bytes() != encoded:
        raise ValueError("frozen D02.var01 diff differs")
    print(json.dumps({"changed_tables_only": list(changed),
                      "unchanged_table_count": result["unchanged_table_count"],
                      "diff_sha256": sha(encoded)}))


if __name__ == "__main__":
    main()
