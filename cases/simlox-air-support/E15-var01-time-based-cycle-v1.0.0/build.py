"""Create one time-based reorder child from accepted E15 default-on-hand stock."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-default.json"
PARENT_SHA = "602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e"


def build() -> str:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    assert len(tables) == len(doc["model"]["tables"]) == 31
    reorder = tables["ItemReorder"]["instances"][0]["rows"]
    assert reorder == [["TEACH-DU-01", "DEPOT-01", 1.0, None, None, None,
                        None, None, None, None, None]]
    stock = tables["StockAllocation"]["instances"][0]["rows"]
    assert stock[1] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2,
                        None, None, None, None]
    reorder[0][5] = 16.0
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "native-input.json"
    if output.exists():
        assert output.read_bytes() == raw, "frozen input differs"
    else:
        output.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


if __name__ == "__main__":
    print(build())
