"""Freeze below-nominal ISTOH from the accepted time-based E15 source."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var01-time-based-cycle-v1.0.0/native-input.json"
PARENT_SHA = "d37bdc10592dff04e521d66276b49f9404dfea0511fac5ea73ef201b02b22b1f"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
document = json.loads(PARENT.read_text(encoding="utf-8-sig"))
tables = document["model"]["tables"]
assert len(tables) == 31
allocation = next(table for table in tables if table["name"] == "StockAllocation")
assert [column["name"] for column in allocation["columns"]] == [
    "POINT", "IID", "STID", "STSIZ", "ROSIZ", "AINST", "ISTOH", "PLID", "NOTE"
]
rows = allocation["instances"][0]["rows"]
assert rows == [
    ["AIR_BASIC", "TEACH-DU-01", "BASE-01", 1, None, None, None, None, None],
    ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, None, None, None],
]
rows[1][6] = 3
raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
target = HERE / "native-input.json"
if target.exists():
    assert target.read_bytes() == raw, "frozen child input differs"
else:
    target.write_bytes(raw)
print(hashlib.sha256(raw).hexdigest())
