"""Freeze a same-time stock ROSIZ change and one scheduled depot OUT transfer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
E15 = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-explicit-three.json"
I02 = HERE.parent / "I02-var02-out-transfer-v1.0.0/native-input.json"
assert hashlib.sha256(E15.read_bytes()).hexdigest() == "bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f"
assert hashlib.sha256(I02.read_bytes()).hexdigest() == "7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0"
transfer_schema = next(t for t in json.loads(I02.read_text(encoding="utf-8-sig"))["model"]["tables"]
                       if t["name"] == "ItemTransfer")
assert [c["name"] for c in transfer_schema["columns"]] == [
    "STFID", "STTID", "IID", "TFTIME", "TFQTY", "TFDT", "NOTE"]


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> str:
    assert arm in ("control", "change")
    doc = json.loads(E15.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {table["name"]: table for table in tables}
    assert len(by_name) == len(tables) == 31
    assert rows(by_name["ProblemDescription"]) == [[
        "E15.var07 tracked stock reorder initial depot on-hand explicit-three"]]
    assert rows(by_name["StockAllocation"])[1][3:7] == [4, 2, None, 3]
    assert rows(by_name["ItemReorder"]) == [[
        "TEACH-DU-01", "DEPOT-01", 1.0, None, None, None, None, None, None, None, None]]
    rows(by_name["ProblemDescription"])[0][0] = "I07.var07 matched same-time depot ROSIZ and OUT transfer"
    change = {
        "name": "ChangesStockAllocation",
        "columns": [
            {"name": name, "datatype": dtype,
             **({"key": True} if name in ("POINT", "IID", "STID", "TIMEC") else {})}
            for name, dtype in (("POINT", "string"), ("IID", "string"), ("STID", "string"),
                                ("TIMEC", "double"), ("ROSIZ", "integer"), ("NOTE", "string"))
        ],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 6],
            "change": [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]],
        }[arm]}],
    }
    transfer = {
        "name": "ItemTransfer",
        "columns": transfer_schema["columns"],
        "instances": [{"instance_name": "", "rows": [
            ["DEPOT-01", "<OUTSIDE>", "TEACH-DU-01", 5.0, 1, 0.0, None]
        ]}],
    }
    insertion = tables.index(by_name["StockAllocation"]) + 1
    tables[insertion:insertion] = [change, transfer]
    payload = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / f"{arm}-input.json"
    if path.exists():
        assert path.read_bytes() == payload, f"frozen {arm} input differs"
    else:
        path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "change"):
        print(arm, make(arm))
