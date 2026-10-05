"""Build frozen later-demand ROSIZ pair from accepted E15 explicit-three."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-explicit-three.json"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == "bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f"


def make(arm: str) -> str:
    assert arm in ("control", "change")
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {t["name"]: t for t in tables}
    assert len(tables) == len(by_name) == 31
    description = by_name["ProblemDescription"]["instances"][0]["rows"]
    assert description == [["E15.var07 tracked stock reorder initial depot on-hand explicit-three"]]
    description[0][0] = "I07.var06 next demand first reorder batch may exceed new ROSIZ"
    stock = by_name["StockAllocation"]["instances"][0]["rows"]
    assert stock[1][3:7] == [4, 2, None, 3]
    stock[1][4] = 3
    assert by_name["ItemReorder"]["instances"][0]["rows"] == [[
        "TEACH-DU-01", "DEPOT-01", 1.0, None, None, None, None, None, None, None, None]]
    change = {"name": "ChangesStockAllocation", "columns": [
        {"name": name, "datatype": dtype,
         **({"key": True} if name in ("POINT", "IID", "STID", "TIMEC") else {})}
        for name, dtype in (("POINT", "string"), ("IID", "string"), ("STID", "string"),
                            ("TIMEC", "double"), ("ROSIZ", "integer"), ("NOTE", "string"))],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 6],
            "change": [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]],
        }[arm]}]}
    tables.insert(tables.index(by_name["StockAllocation"]) + 1, change)
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / f"{arm}-input.json"
    if path.exists():
        assert path.read_bytes() == raw, f"frozen {arm} input differs"
    else:
        path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "change"):
        print(arm, make(arm))
