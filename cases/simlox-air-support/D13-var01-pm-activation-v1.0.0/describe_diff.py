"""Verify the exact D13.var01 profile delta from accepted D03."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "parent-diff.json"
PARENT_SHA = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
CHILD_SHA = "f4fce5c8f362be817264544f22f271c1ee47b6e635e871619525fa1c8545ca70"


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
    added = {n: child[n] for n in child if n not in parent}
    if set(changed) != {"ProblemDescription"} or set(added) != {"PMActivation", "PMActivationProfile"}:
        raise ValueError("unexpected parent delta")
    result = {"schema": "simlox-d13-var01-exact-parent-diff/v1",
              "case_id": "D13", "variant_id": "D13.var01", "version": "1.0.0-candidate",
              "parent_input_sha256": PARENT_SHA, "child_input_sha256": CHILD_SHA,
              "changed_tables_only": list(changed), "added_tables_only": list(added),
              "unchanged_table_count": len(parent) - len(changed),
              "changed_tables": changed, "added_tables": added,
              "publication_state": "not_published"}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(encoded)
    elif OUT.read_bytes() != encoded:
        raise ValueError("frozen D13.var01 diff differs")
    print(json.dumps({"changed_tables_only": list(changed),
                      "added_tables_only": list(added), "unchanged_table_count":
                      result["unchanged_table_count"], "diff_sha256": sha(encoded)}))


if __name__ == "__main__":
    main()
