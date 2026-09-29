"""Verify the exact D02.var02 CALHOURS delta from accepted D06."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "parent-diff.json"
PARENT_SHA = "ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78"
CHILD_SHA = "23b550dbc4e0aea4d6d328fe4805a4eb50af81f3af54ccd6353e45bce933271b"


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
    if set(parent) != set(child) or set(changed) != {"ProblemDescription", "FailureMode"}:
        raise ValueError("unexpected D02.var02 parent delta")
    result = {"schema": "simlox-d02-var02-calendar-exact-parent-diff/v1",
              "case_id": "D02", "variant_id": "D02.var02", "version": "1.0.0-candidate",
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
        raise ValueError("frozen D02.var02 diff differs")
    print(json.dumps({"changed_tables_only": list(changed),
                      "unchanged_table_count": result["unchanged_table_count"],
                      "diff_sha256": sha(encoded)}))


if __name__ == "__main__":
    main()
