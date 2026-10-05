"""Freeze one NFFF=0 source cell from the accepted E14 seed-2 extra arm."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E14-var01-02-extra-removal-v1.0.0/seed2-extra-input.json"
PARENT_SHA = "531a1f99e45b71ad0137aaf18650e3df84cec77a677beadaad7d35e4fdb84a75"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
document = json.loads(PARENT.read_text(encoding="utf-8-sig"))
tables = document["model"]["tables"]
assert len(tables) == 31
structure = next(t for t in tables if t["name"] == "ItemStructure")
assert [c["name"] for c in structure["columns"]] == [
    "IID", "MID", "QTYPM", "ENVF", "RRF", "RUBM", "NFFF", "NFFT", "NOTE"
]
rows = structure["instances"][0]["rows"]
assert rows == [
    ["TEACH-LRU-01", "TEACH-AIR-01", 1, 1.0, None, None, None, None, None],
    ["TEACH-SRU-01", "TEACH-LRU-01", 1, 1.0, 4.0, None, 2.0, 0.25, None],
    ["TEACH-SRU-02", "TEACH-LRU-01", 1, 1.0, 4.0, None, 2.0, 0.25, None],
]
rows[1][6] = 0.0
raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
target = HERE / "native-input.json"
if target.exists():
    assert target.read_bytes() == raw, "frozen child input differs"
else:
    target.write_bytes(raw)
print(hashlib.sha256(raw).hexdigest())
