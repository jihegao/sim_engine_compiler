"""Derive a terminal in-progress system repair from accepted D01 bytes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D01-system-direct-repair-v1.0.0" / "native-input.json"
PARENT_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
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

    def set_cell(table: str, row_number: int, column: str, before: object, after: object) -> None:
        t = tables[table]
        fields = [c["name"] for c in t["columns"]]
        if len(t["instances"]) != 1 or fields.count(column) != 1:
            raise ValueError(f"unexpected {table} shape")
        rows = t["instances"][0]["rows"]
        if row_number >= len(rows) or len(rows[row_number]) != len(fields):
            raise ValueError(f"unexpected {table} row")
        row = rows[row_number]
        pos = fields.index(column)
        if row[pos] != before:
            raise ValueError(f"unexpected {table}.{column} parent value")
        row[pos] = after

    set_cell("ProblemDescription", 0, "PDESC",
             "D01 system-level direct repair: one aircraft, fixed 0.5 h repair, stochastic operational failure",
             "D01.var03 terminal h34.375 with system direct repair still in progress")
    set_cell("Control", 0, "SIMPE", 36.0, 34.375)
    set_cell("Control", 0, "RCINT", 0.5, 0.125)
    set_cell("Control", 0, "RCEND", 36.0, 34.375)
    for row_number in (0, 1):
        set_cell("ResultCollection", row_number, "RCINT", 0.5, 0.125)
        set_cell("ResultCollection", row_number, "RCEND", 36.0, 34.375)
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
        raise ValueError("frozen D01.var03 input differs from generator")
    print(json.dumps({"variant_id": "D01.var03", "parent_sha256": PARENT_SHA,
                      "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
