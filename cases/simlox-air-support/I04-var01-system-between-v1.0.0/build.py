"""Freeze a two-arm system BETWEEN transfer from accepted A17."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
PARENT_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> str:
    assert arm in ("control", "between")
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {t["name"]: t for t in tables}
    assert len(by_name) == len(tables)
    assert rows(by_name["SystemDeployment"]) == [
        ["TEACH-AIR-01", "TEACH-UNIT", 1, 1, None, None, None],
        ["TEACH-AIR-01", "TEACH-UNIT-2", 1, 1, None, None, None],
    ]
    profile = rows(by_name["OperationProfile"])
    assert profile == [["BASIC-SCHEDULE", "BASIC-MISSION", 8.0, "SCHEDULED", 1, None, 0, None, 1 / 3, None, None, None]]
    second = profile[0].copy()
    second[2] = 20.0
    profile.append(second)
    assert rows(by_name["ProblemDescription"]) == [["A17 two explicit units at two bases serving one group mission; no transfer"]]
    rows(by_name["ProblemDescription"])[0][0] = f"I04.var01 {arm}: scheduled BETWEEN after first group mission"
    transfer = {
        "name": "SystemTransfer",
        "columns": [
            {"name": name, "datatype": dtype, **({"key": True} if name in ("UFID", "UTID", "SID", "TFTIME") else {})}
            for name, dtype in (
                ("UFID", "string"), ("UTID", "string"), ("SID", "string"),
                ("TFTIME", "double"), ("TFQTY", "integer"), ("TFDT", "double"),
                ("TFPRI", "integer"), ("NOTE", "string")
            )
        ],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 8],
            "between": [["TEACH-UNIT", "TEACH-UNIT-2", "TEACH-AIR-01", 8.5, 1, 0.5, None, None]],
        }[arm]}],
    }
    tables.insert(tables.index(by_name["SystemDeployment"]) + 1, transfer)
    out = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == out, f"frozen {arm} source differs"
    else:
        target.write_bytes(out)
    return hashlib.sha256(out).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "between"):
        print(arm, make(arm))
