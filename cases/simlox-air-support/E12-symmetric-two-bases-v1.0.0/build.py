"""Freeze E12's two symmetric operational bases from accepted E07."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E07-item-specific-transport-v1.0.1/native-input.json"
PARENT_SHA = "d42832b9e17b9a0c968a8bba7bcb1419eba06313097604fc0041baab5d132bc0"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12 two symmetric BASE-01 instances with one local spare and one aircraft each"
    )
    station = table(doc, "Station")
    names = [c["name"] for c in station["columns"]]
    rows = station["instances"][0]["rows"]
    assert [(r[names.index("STID")], r[names.index("QTY")]) for r in rows] == [
        ("BASE-01", 1), ("DEPOT-01", 1)
    ]
    rows[0][names.index("QTY")] = 2
    stock = table(doc, "StockAllocation")
    names = [c["name"] for c in stock["columns"]]
    rows = stock["instances"][0]["rows"]
    assert [(r[names.index("STID")], r[names.index("STSIZ")]) for r in rows] == [
        ("BASE-01", 0), ("DEPOT-01", 1)
    ]
    rows[0][names.index("STSIZ")] = 1
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
