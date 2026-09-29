"""Regenerate or verify D05's exact table and field delta from accepted D03."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D03-calendar-pm-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "parent-diff.json"
PARENT_SHA256 = "5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32"
CHILD_SHA256 = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(table: dict) -> list[dict]:
    columns = [x["name"] for x in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for instance in table["instances"]
            for row in instance["rows"]]


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--write", action="store_true")
    parsed = args.parse_args()
    parent_raw, child_raw = PARENT.read_bytes(), CHILD.read_bytes()
    if sha(parent_raw) != PARENT_SHA256 or sha(child_raw) != CHILD_SHA256:
        raise ValueError("source fingerprint differs")
    parent = json.loads(parent_raw)["model"]["tables"]
    child = json.loads(child_raw)["model"]["tables"]
    if [x["name"] for x in parent] != [x["name"] for x in child]:
        raise ValueError("native table list/order differs")
    changed = {a["name"]: {"parent_rows": rows(a), "child_rows": rows(b)}
               for a, b in zip(parent, child, strict=True) if a != b}
    result = {
        "schema": "simlox-d05-exact-parent-diff/v1", "case_id": "D05", "version": "1.0.0-candidate",
        "parent_case": "D03@1.0.0", "parent_input_sha256": PARENT_SHA256,
        "child_input_sha256": CHILD_SHA256,
        "changed_tables_only": list(changed), "unchanged_table_count": len(parent) - len(changed),
        "tables": changed, "publication_state": "not_published",
    }
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if parsed.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(encoded)
    elif OUT.read_bytes() != encoded:
        raise ValueError("parent diff differs")
    print(json.dumps({"changed_tables_only": list(changed), "unchanged_table_count":
                      result["unchanged_table_count"], "diff_sha256": sha(encoded)}))


if __name__ == "__main__":
    main()
