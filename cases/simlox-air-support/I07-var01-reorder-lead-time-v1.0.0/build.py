"""Freeze a scheduled reorder lead-time change from accepted E15.var07."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1" / "native-input-explicit-three.json"
PARENT_SHA = "bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> str:
    assert arm in ("control", "change")
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {table["name"]: table for table in tables}
    assert len(by_name) == len(tables) == 31
    assert rows(by_name["ItemReorder"]) == [["TEACH-DU-01", "DEPOT-01", 1.0, None, None, None, None, None, None, None, None]]
    assert rows(by_name["ProblemDescription"]) == [["E15.var07 tracked stock reorder initial depot on-hand explicit-three"]]
    rows(by_name["ProblemDescription"])[0][0] = f"I07.var01 {arm}: scheduled depot reorder lead time"
    change = {
        "name": "ChangesItemReorder",
        "columns": [
            {"name": name, "datatype": dtype, **({"key": True} if name in ("IID", "STID", "TIMEC") else {})}
            for name, dtype in (
                ("IID", "string"), ("STID", "string"), ("TIMEC", "double"),
                ("LEADT", "double"), ("DISCF", "double"), ("LEADTD", "string"),
                ("ROINT", "double"), ("NOTE", "string")
            )
        ],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 8],
            "change": [["TEACH-DU-01", "DEPOT-01", 5.0, 3.0, None, None, None, None]],
        }[arm]}],
    }
    tables.insert(tables.index(by_name["ItemReorder"]) + 1, change)
    out = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == out, f"frozen {arm} input differs"
    else:
        target.write_bytes(out)
    return hashlib.sha256(out).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "change"):
        print(arm, make(arm))
