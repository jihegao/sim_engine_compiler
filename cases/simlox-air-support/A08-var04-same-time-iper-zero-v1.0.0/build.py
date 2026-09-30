"""Derive simultaneous random-profile missions from accepted A08.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A08-var01-fixed-count-random-time-v1.0.0" / "native-input.json"
PARENT_SHA = "df7ecf0549fc8b1a506095194b97dac810afc395a76b4c478cfe43eec1838920"
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
        raise ValueError("accepted A08.var01 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    set_one(doc, "ProblemDescription", "PDESC",
            "A08.var01 three random-time missions per period, 32 replications",
            "A08.var04 three simultaneous missions at hour 8, 32 replications")
    set_one(doc, "OperationProfile", "IPER", 12.0, 0.0)
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
