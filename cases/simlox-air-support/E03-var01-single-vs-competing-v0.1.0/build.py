"""Derive the single-demand E03 variant from the byte-pinned accepted E03 input."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E03-two-aircraft-shared-spare-v1.0.0" / "native-input.json"
PARENT_SHA256 = "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA256:
        raise ValueError("accepted E03 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table name")

    def set_one(table: str, column: str, before: object, after: object) -> None:
        t = tables[table]
        names = [c["name"] for c in t["columns"]]
        instances = t["instances"]
        if len(instances) != 1 or len(instances[0]["rows"]) != 1:
            raise ValueError(f"unexpected {table} shape")
        row = instances[0]["rows"][0]
        if len(row) != len(names) or names.count(column) != 1 or row[names.index(column)] != before:
            raise ValueError(f"unexpected {table}.{column} parent value")
        row[names.index(column)] = after

    set_one("OperationProfile", "IQTY", 2, 1)
    desc = tables["ProblemDescription"]["instances"][0]["rows"][0]
    cols = [c["name"] for c in tables["ProblemDescription"]["columns"]]
    if len(desc) != len(cols) or cols.count("PDESC") != 1:
        raise ValueError("unexpected description shape")
    desc[cols.index("PDESC")] = "E03.var01 one scheduled mission with two deployed aircraft and one local spare"
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(f"refusing to overwrite {OUTPUT}")
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen E03.var01 input differs from generator")
    print(json.dumps({"variant_id": "E03.var01", "parent_sha256": PARENT_SHA256, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
