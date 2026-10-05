"""Build the matched zero-FRT control from the byte-pinned accepted D01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-installed-lru-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93"
OUTPUT = HERE / "native-input.json"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted D01 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    if len(tables) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table name")

    def set_one(table: str, column: str, before: object, after: object) -> None:
        t = tables[table]
        fields = [c["name"] for c in t["columns"]]
        instances = t["instances"]
        if len(instances) != 1 or len(instances[0]["rows"]) != 1:
            raise ValueError(f"unexpected {table} shape")
        row = instances[0]["rows"][0]
        if len(row) != len(fields) or fields.count(column) != 1 or row[fields.index(column)] != before:
            raise ValueError(f"unexpected {table}.{column} parent value")
        row[fields.index(column)] = after

    set_one("System", "FRT", 300000, 0)
    set_one("Item", "FRT", 300000, 0)
    set_one("ProblemDescription", "PDESC",
            "D01 installed LRU: one local spare, system replacement, direct item repair",
            "D01.var01 matched zero-failure control with installed LRU and one local spare")
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
        raise ValueError("frozen D01.var01 input differs from generator")
    print(json.dumps({"variant_id": "D01.var01", "parent_sha256": PARENT_SHA,
                      "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
