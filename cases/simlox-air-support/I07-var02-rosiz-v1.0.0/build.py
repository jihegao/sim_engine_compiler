"""Freeze matched I07.var02 inputs from accepted E15 explicit-three stock."""
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
    document = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = document["model"]["tables"]
    by_name = {table["name"]: table for table in tables}
    assert len(by_name) == len(tables) == 31
    assert rows(by_name["ProblemDescription"]) == [["E15.var07 tracked stock reorder initial depot on-hand explicit-three"]]
    assert rows(by_name["StockAllocation"]) == [
        ["AIR_BASIC", "TEACH-DU-01", "BASE-01", 1, None, None, None, None, None],
        ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, 3, None, None],
    ]
    assert rows(by_name["ItemReorder"]) == [["TEACH-DU-01", "DEPOT-01", 1.0, None, None, None, None, None, None, None, None]]
    assert rows(by_name["Item"])[0][21] == "Y"  # TRACK enables station ItemResults.
    rows(by_name["ProblemDescription"])[0][0] = "I07.var02 matched scheduled depot ROSIZ contrast"
    change = {
        "name": "ChangesStockAllocation",
        "columns": [
            {"name": name, "datatype": dtype, **({"key": True} if name in ("POINT", "IID", "STID", "TIMEC") else {})}
            for name, dtype in (
                ("POINT", "string"), ("IID", "string"), ("STID", "string"),
                ("TIMEC", "double"), ("ROSIZ", "integer"), ("NOTE", "string"),
            )
        ],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 6],
            "change": [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]],
        }[arm]}],
    }
    tables.insert(tables.index(by_name["StockAllocation"]) + 1, change)
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == payload, f"frozen {arm} input differs"
    else:
        target.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "change"):
        print(arm, make(arm))
