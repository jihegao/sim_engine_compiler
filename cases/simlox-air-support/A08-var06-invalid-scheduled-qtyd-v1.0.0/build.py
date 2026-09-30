"""Derive invalid SCHEDULED plus IQTYD boundary from accepted A08.var02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A08-var02-random-count-equidist-v1.0.0" / "native-input.json"
PARENT_SHA = "54e1fab467ede59829b0c8994aa4d72f1e08878cf7a39532c6fe61364ca87c84"
OUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def one(doc: dict, name: str) -> tuple[list[str], list[list]]:
    table, = (t for t in doc["model"]["tables"] if t["name"] == name)
    instance, = table["instances"]
    return [c["name"] for c in table["columns"]], instance["rows"]


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    columns, rows = one(doc, name)
    if len(rows) != 1 or field not in columns or rows[0][columns.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    rows[0][columns.index(field)] = after


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted A08.var02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    set_one(doc, "ProblemDescription", "PDESC",
            "A08.var02 Poisson mission count, equidistant over one 12-hour period",
            "A08.var06 invalid SCHEDULED with IQTYD Poisson diagnostic probe")
    set_one(doc, "OperationProfile", "ITYPE", "RANDOM", "SCHEDULED")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"native_input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
