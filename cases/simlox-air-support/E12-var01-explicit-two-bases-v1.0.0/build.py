"""Freeze two individually named bases as the E12 QTY=2 comparator."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-symmetric-two-bases-v1.0.0/native-input.json"
PARENT_SHA = "a258878494ed6833e9a211200cfcad7f97b272af278b51285e01be035d61f122"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def clone_row(doc: dict, name: str, field: str, old_value: str, changes: dict[str, object], *, insert_at: int | None = None) -> None:
    t = table(doc, name)
    columns = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    matches = [row for row in rows if row[columns.index(field)] == old_value]
    assert len(matches) == 1, (name, field, old_value)
    row = copy.deepcopy(matches[0])
    for column, value in changes.items():
        row[columns.index(column)] = value
    if insert_at is None:
        rows.append(row)
    else:
        rows.insert(insert_at, row)


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var01 two explicit bases with one unit, aircraft and local spare per base"
    )
    station = table(doc, "Station")
    snames = [c["name"] for c in station["columns"]]
    assert station["instances"][0]["rows"][0][snames.index("QTY")] == 2
    station["instances"][0]["rows"][0][snames.index("QTY")] = 1
    clone_row(doc, "Station", "STID", "BASE-01", {"STID": "BASE-02", "DESCR": "Second teaching base"}, insert_at=1)
    clone_row(doc, "StationStructure", "STID", "BASE-01", {"STID": "BASE-02"})
    clone_row(doc, "ItemStationStructure", "STID", "BASE-01", {"STID": "BASE-02"})
    clone_row(doc, "SystemRepair", "STID", "BASE-01", {"STID": "BASE-02"})
    clone_row(doc, "StockAllocation", "STID", "BASE-01", {"STID": "BASE-02"})
    clone_row(doc, "Unit", "UNID", "TEACH-UNIT", {"UNID": "TEACH-UNIT-2", "DESCR": "Second one-aircraft teaching unit", "STID": "BASE-02"})
    clone_row(doc, "SystemDeployment", "USTID", "TEACH-UNIT", {"USTID": "TEACH-UNIT-2"})
    clone_row(doc, "Operations", "USTID", "TEACH-UNIT", {"USTID": "TEACH-UNIT-2"})
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


if __name__ == "__main__":
    output = HERE / "native-input.json"
    raw = build()
    if sys.argv[1:] == ["--write"]:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: build.py [--write]")
    else:
        assert output.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))
