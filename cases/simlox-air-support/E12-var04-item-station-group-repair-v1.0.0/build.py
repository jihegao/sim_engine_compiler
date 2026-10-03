"""Freeze the Item.GIID by Station.GSTID depot ItemRepair intersection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var03-base02-system-repair-override-v1.0.0/native-input.json"
PARENT_SHA = "568123c14daa026aa4665906abf4173ee6ed008373e2d2da9b710e9b153d61b6"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var04 LRU-GRP by DEPOT-GRP ItemRepair intersection with BASE-02 SystemRepair override"
    )
    item = table(doc, "Item")
    item_cols = [c["name"] for c in item["columns"]]
    assert len(item["instances"][0]["rows"]) == 1
    item_row = item["instances"][0]["rows"][0]
    assert item_row[item_cols.index("IID")] == "TEACH-LRU-01" and item_row[item_cols.index("GIID")] is None
    item_row[item_cols.index("GIID")] = "LRU-GRP"
    station = table(doc, "Station")
    station_cols = [c["name"] for c in station["columns"]]
    depot = [r for r in station["instances"][0]["rows"] if r[station_cols.index("STID")] == "DEPOT-01"]
    assert len(depot) == 1 and depot[0][station_cols.index("GSTID")] is None
    depot[0][station_cols.index("GSTID")] = "DEPOT-GRP"
    repair = table(doc, "ItemRepair")
    repair_cols = [c["name"] for c in repair["columns"]]
    assert len(repair["instances"][0]["rows"]) == 1
    row = repair["instances"][0]["rows"][0]
    assert row[repair_cols.index("IID")] == "TEACH-LRU-01" and row[repair_cols.index("STID")] == "DEPOT-01" and row[repair_cols.index("DIRPT")] == 1.0
    row[repair_cols.index("IID")] = "LRU-GRP"
    row[repair_cols.index("STID")] = "DEPOT-GRP"
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
