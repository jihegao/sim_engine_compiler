"""Freeze an E09 depot backorder-priority three-arm native contrast."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "E12-var02-two-fault-control-v1.0.0/native-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "65f6790c712552ff8fd6db322a2a9f5e345d3e9679cb28bea4a15f781a55dd3b"


def table(document, name):
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def row(table_name, key_column, key_value, document):
    t = table(document, table_name)
    cols = [c["name"] for c in t["columns"]]
    index = cols.index(key_column)
    found = [r for instance in t["instances"] for r in instance["rows"] if r[index] == key_value]
    assert len(found) == 1, (table_name, key_column, key_value, len(found))
    return cols, found[0]


def change(document, name, key_column, key_value, column, expected, value):
    cols, target = row(name, key_column, key_value, document)
    index = cols.index(column)
    assert target[index] == expected, (name, key_value, column, target[index])
    target[index] = value


for arm, enbop, bopri in (("fifo", "Y", "N"), ("priority", "Y", "Y"), ("disabled", "N", "Y")):
    doc = json.loads(parent.read_text(encoding="utf-8"))
    assert len(doc["model"]["tables"]) == 32
    change(doc, "ProblemDescription", "PDESC", "E12.var02 individual SystemRepair control with 3.5-hour missions at two bases", "PDESC", "E12.var02 individual SystemRepair control with 3.5-hour missions at two bases", f"E09 {arm} one depot item, ordinary BASE-01 request versus BASE-02 aircraft backorder")
    change(doc, "Control", "NREPS", 1, "ENBOP", None, enbop)
    change(doc, "Station", "STID", "DEPOT-01", "BOPRI", None, bopri)
    allocation = table(doc, "StockAllocation")
    columns = [c["name"] for c in allocation["columns"]]
    stid, stsiz = columns.index("STID"), columns.index("STSIZ")
    rows = [r for instance in allocation["instances"] for r in instance["rows"] if any(v is not None for v in r)]
    assert len(rows) == 3 and {r[stid]: r[stsiz] for r in rows} == {"BASE-01": 1, "BASE-02": 1, "DEPOT-01": 1}
    for r in rows:
        if r[stid] in ("BASE-02", "DEPOT-01"):
            r[stsiz] = 0
    payload = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == payload, f"frozen {arm} input changed"
    else:
        target.write_bytes(payload)
    print(arm, hashlib.sha256(payload).hexdigest())
