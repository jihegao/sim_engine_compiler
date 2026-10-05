"""Freeze a single additional-initial-stock cell from accepted E15 default."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-default.json"
PARENT_SHA = "602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
document = json.loads(PARENT.read_text(encoding="utf-8-sig"))
tables = document["model"]["tables"]
by_name = {table["name"]: table for table in tables}
assert len(tables) == len(by_name) == 31
stock = by_name["StockAllocation"]
assert [column["name"] for column in stock["columns"]] == [
    "POINT", "IID", "STID", "STSIZ", "ROSIZ", "AINST", "ISTOH", "PLID", "NOTE"
]
assert stock["instances"][0]["rows"] == [
    ["AIR_BASIC", "TEACH-DU-01", "BASE-01", 1, None, None, None, None, None],
    ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, None, None, None],
]
stock["instances"][0]["rows"][1][5] = 2
raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
target = HERE / "native-input.json"
if target.exists():
    assert target.read_bytes() == raw, "frozen input differs"
else:
    target.write_bytes(raw)
print(hashlib.sha256(raw).hexdigest())
