"""Freeze one later LEADT change from the accepted I07.var01 early-change arm."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I07-var01-reorder-lead-time-v1.0.0" / "change-input.json"
PARENT_SHA = "4269922f65f8c3ecee867451c2a4c308287c42ebb7c974af93618c7e4e1138e0"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA

document = json.loads(PARENT.read_text(encoding="utf-8-sig"))
tables = document["model"]["tables"]
by_name = {table["name"]: table for table in tables}
assert len(by_name) == len(tables) == 32
assert by_name["ProblemDescription"]["instances"][0]["rows"] == [
    ["I07.var01 change: scheduled depot reorder lead time"]]
assert by_name["ItemReorder"]["instances"][0]["rows"] == [
    ["TEACH-DU-01", "DEPOT-01", 1.0, None, None, None, None, None, None, None, None]]
change = by_name["ChangesItemReorder"]["instances"][0]["rows"]
assert change == [["TEACH-DU-01", "DEPOT-01", 5.0, 3.0, None, None, None, None]]
assert by_name["StockAllocation"]["instances"][0]["rows"][1][3:7] == [4, 2, None, 3]
by_name["ProblemDescription"]["instances"][0]["rows"][0][0] = (
    "I07.var03 outstanding depot reorder retains original lead time")
change[0][2] = 10.5
payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
target = HERE / "late-input.json"
if target.exists():
    assert target.read_bytes() == payload, "frozen late input differs"
else:
    target.write_bytes(payload)
print(hashlib.sha256(payload).hexdigest())
