"""Freeze Station LEVL/LINDX metadata contrast from accepted E12.var05."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var05-base02-zero-opening-stock-v1.0.0/native-input.json"
PARENT_SHA = "940592a6e27a84549e57656921ca111c1fc3c16e0bf233b90259866afb81071b"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var06 station LEVL/LINDX report layout metadata, asymmetric stock retained"
    )
    station = table(doc, "Station")
    names = [c["name"] for c in station["columns"]]
    rows = station["instances"][0]["rows"]
    assert len(rows) == 3
    desired = {"BASE-01": ("BASE", 2), "BASE-02": ("BASE", 1), "DEPOT-01": ("DEPOT", 1)}
    assert {row[names.index("STID")] for row in rows} == set(desired)
    for row in rows:
        assert row[names.index("LEVL")] is None and row[names.index("LINDX")] is None
        row[names.index("LEVL")], row[names.index("LINDX")] = desired[row[names.index("STID")]]
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
