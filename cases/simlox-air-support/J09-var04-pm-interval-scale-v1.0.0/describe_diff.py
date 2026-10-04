"""Certify the exact one-table delta from accepted D03 calendar PM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import FIELDS, HERE, PARENT_INPUT, PARENT_SHA, OUTPUT

DIFF = HERE / "exact-diff.json"
SOURCE_SHA = "e58a615dca7dca19608cee4546940d3823188559d49c37604ffbe6d064777486"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe() -> dict:
    if sha(PARENT_INPUT) != PARENT_SHA or sha(OUTPUT) != SOURCE_SHA:
        raise ValueError("frozen input fingerprint differs")
    before = json.loads(PARENT_INPUT.read_bytes())
    after = json.loads(OUTPUT.read_bytes())
    original_tables = before["model"]["tables"]
    scaled_tables = after["model"]["tables"]
    if len(scaled_tables) != len(original_tables) + 1 or scaled_tables[:-1] != original_tables:
        raise ValueError("existing table changed")
    before["model"]["tables"] = scaled_tables
    if before != after:
        raise ValueError("non-table model data changed")
    scale = scaled_tables[-1]
    if scale["name"] != "ScaleFactors" or [c["name"] for c in scale["columns"]] != list(FIELDS):
        raise ValueError("unexpected scale table")
    if [c["datatype"] for c in scale["columns"]] != ["double"] * 6:
        raise ValueError("unexpected scale data types")
    if scale["instances"] != [{"instance_name": "", "rows": [[1.0, 1.0, 1.0, 2.0, 1.0, 1.0]]}]:
        raise ValueError("unexpected scale row")
    return {"schema": "simlox-j09-var04-exact-diff/v1", "parent_input_sha256": PARENT_SHA,
            "scaled_input_sha256": SOURCE_SHA, "unchanged_existing_tables": len(original_tables),
            "appended_table": scale, "other_changes": []}


if __name__ == "__main__":
    raw = (json.dumps(describe(), indent=2) + "\n").encode()
    if not DIFF.exists():
        DIFF.write_bytes(raw)
    elif DIFF.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(json.dumps({"exact_diff_sha256": hashlib.sha256(raw).hexdigest()}))
