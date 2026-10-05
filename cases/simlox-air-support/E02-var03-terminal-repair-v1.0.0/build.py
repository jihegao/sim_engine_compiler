"""Freeze the E02.var03 h11 terminal-repair child from accepted E02."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E02-zero-stock-local-backorder-v1.0.0" / "native-input.json"
OUTPUT = HERE / "native-input.json"
PARENT_SHA256 = "12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> bytes:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256, "accepted E02 parent input differs"
    document = json.loads(raw)
    tables = {table["name"]: table for table in document["model"]["tables"]}
    control = tables["Control"]["instances"][0]["rows"]
    control_columns = [column["name"] for column in tables["Control"]["columns"]]
    assert len(control) == 1
    for name in ("SIMPE", "RCEND"):
        index = control_columns.index(name)
        assert control[0][index] == 36.0
        control[0][index] = 11.0
    result = tables["ResultCollection"]["instances"][0]["rows"]
    result_columns = [column["name"] for column in tables["ResultCollection"]["columns"]]
    assert [row[result_columns.index("RTYPE")] for row in result] == ["MISSION", "SYSTEM"]
    for row in result:
        index = result_columns.index("RCEND")
        assert row[index] == 36.0
        row[index] = 11.0
    operation = tables["OperationProfile"]["instances"][0]["rows"]
    operation_columns = [column["name"] for column in tables["OperationProfile"]["columns"]]
    assert [row[operation_columns.index("STIM")] for row in operation] == [8.0, 20.0, 32.0]
    assert all(row[operation_columns.index("SPRID")] == "BASIC-MISSION" for row in operation)
    del operation[1:]
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    built = build()
    if OUTPUT.exists():
        assert OUTPUT.read_bytes() == built, "frozen child input differs"
    else:
        OUTPUT.write_bytes(built)
    print(json.dumps({"parent_sha256": PARENT_SHA256, "child_sha256": sha(built), "bytes": len(built)}))
