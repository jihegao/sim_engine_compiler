"""Freeze matched MINBS=1/2 same-item arms from accepted E10 ONDEM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "E10-var01-fixed-ondem-v1.0.1/native-input-ondem.json"
PARENT_SHA = "1ad095c4d1d371c1a2b8e7bc61d629e59459eff90ff310e5c6d1945c4cf70882"
SUPPORT = ROOT / "E03-two-aircraft-shared-spare-v1.0.0/native-input.json"
SUPPORT_SHA = "657c0d52116c09ef2dbd009209f461f6fb4ed3570327c4305e0e4608f208cbf0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def first_row(t: dict) -> list:
    rows = [row for inst in t["instances"] for row in inst["rows"]]
    assert len(rows) == 1, t["name"]
    return rows[0]


def get(t: dict, row: list, field: str):
    return row[[c["name"] for c in t["columns"]].index(field)]


def set_one(t: dict, row: list, field: str, old, new) -> None:
    index = [c["name"] for c in t["columns"]].index(field)
    assert row[index] == old, (t["name"], field, row[index], old)
    row[index] = new


def build(minbs: int) -> bytes:
    assert minbs in (1, 2)
    assert sha(PARENT) == PARENT_SHA and sha(SUPPORT) == SUPPORT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    e03 = json.loads(SUPPORT.read_text(encoding="utf-8-sig"))
    description = first_row(table(doc, "ProblemDescription"))
    description[0] = f"E10.var06 same-item ONDEM batch threshold MINBS={minbs}; two aircraft and two demands"
    for name in ("System", "Item"):
        target = table(doc, name)
        row = first_row(target)
        support = table(e03, name)
        support_row = first_row(support)
        assert get(support, support_row, "FRT") == 3000000
        set_one(target, row, "FRT", 300000, 3000000)
    deploy = table(doc, "SystemDeployment")
    assert get(table(e03, "SystemDeployment"), first_row(table(e03, "SystemDeployment")), "QTYPS") == 2
    set_one(deploy, first_row(deploy), "QTYPS", 1, 2)
    profile = table(doc, "OperationProfile")
    support_profile = table(e03, "OperationProfile")
    assert profile["columns"] == support_profile["columns"]
    assert len(profile["instances"]) == len(support_profile["instances"]) == 1
    assert len(profile["instances"][0]["rows"]) == 3
    support_rows = support_profile["instances"][0]["rows"]
    assert support_rows == [["BASIC-SCHEDULE", "BASIC-MISSION", 8.0, "SCHEDULED", 2, None, 0, None, 1 / 3, None, None, None]]
    profile["instances"][0]["rows"] = [support_rows[0].copy()]
    stock = table(doc, "StockAllocation")
    stock_rows = stock["instances"][0]["rows"]
    assert len(stock_rows) == 2
    depot = next(row for row in stock_rows if get(stock, row, "STID") == "DEPOT-01")
    set_one(stock, depot, "STSIZ", 1, 2)
    transport = table(doc, "TransportPolicyProfile")
    trow = first_row(transport)
    set_one(transport, trow, "MINBS", 1, minbs)
    assert get(transport, trow, "STPRID") == "ONDEM" and get(transport, trow, "TPTIM") == 2.0
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    for minbs in (1, 2):
        path = HERE / f"native-input-minbs{minbs}.json"
        raw = build(minbs)
        if write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
        print(json.dumps({"minbs": minbs, "parent_sha256": PARENT_SHA, "support_sha256": SUPPORT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
