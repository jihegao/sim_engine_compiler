"""Freeze one shorter interval change on accepted E15.var01 time-based parent."""
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
by_name = {table["name"]: table for table in tables}
assert len(tables) == len(by_name) == 31
assert by_name["ItemReorder"]["instances"][0]["rows"] == [
    ["TEACH-DU-01", "DEPOT-01", 1.0, None, None, 16.0, None, None, None, None, None]
]
change = {
    "name": "ChangesItemReorder",
    "columns": [
        {"name": name, "datatype": dtype, **({"key": True} if name in ("IID", "STID", "TIMEC") else {})}
        for name, dtype in (
            ("IID", "string"), ("STID", "string"), ("TIMEC", "double"),
            ("LEADT", "double"), ("DISCF", "double"), ("LEADTD", "string"),
            ("ROINT", "double"), ("NOTE", "string"),
        )
    ],
    "instances": [{"instance_name": "", "rows": [[
        "TEACH-DU-01", "DEPOT-01", 5.0, 1.0, None, None, 8.0, None
    ]]}],
}
tables.insert(tables.index(by_name["ItemReorder"]) + 1, change)
raw = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
target = HERE / "native-input.json"
if target.exists():
    assert target.read_bytes() == raw, "frozen input differs"
else:
    target.write_bytes(raw)
print(hashlib.sha256(raw).hexdigest())
