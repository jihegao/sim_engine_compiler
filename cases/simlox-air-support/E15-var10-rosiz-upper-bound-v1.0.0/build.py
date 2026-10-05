"""Freeze one E15 stock-based ROSIZ above the documented STSIZ+1 limit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-explicit-three.json"
PARENT_SHA = "bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f"


def build() -> str:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    assert len(tables) == len(doc["model"]["tables"]) == 31
    stock = tables["StockAllocation"]["instances"][0]["rows"]
    assert stock[1] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, 3, None, None]
    assert tables["ItemReorder"]["instances"][0]["rows"] == [
        ["TEACH-DU-01", "DEPOT-01", 1.0, None, None, None, None, None, None, None, None]
    ]
    stock[1][4] = 6  # documented maximum is STSIZ + 1 = 5
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "native-input.json"
    if output.exists():
        assert output.read_bytes() == raw, "frozen input differs"
    else:
        output.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    print(build())
