"""Freeze BASE-02 zero-opening-stock contrast from accepted E12.var04."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var04-item-station-group-repair-v1.0.0/native-input.json"
PARENT_SHA = "8ade0fe65e3a46095d8eb3a928a8c577d20b530bf92635e3cee713e05286db73"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var05 BASE-02 zero opening LRU stock versus BASE-01 stocked, group ItemRepair retained"
    )
    stock = table(doc, "StockAllocation")
    names = [c["name"] for c in stock["columns"]]
    rows = stock["instances"][0]["rows"]
    found = [r for r in rows if r[names.index("POINT")] == "AIR_BASIC" and r[names.index("IID")] == "TEACH-LRU-01" and r[names.index("STID")] == "BASE-02"]
    assert len(rows) == 3 and len(found) == 1 and found[0][names.index("STSIZ")] == 1
    found[0][names.index("STSIZ")] = 0
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
