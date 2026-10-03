"""Freeze the two-base group-repair arm at 3.5-hour mission exposure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E12-var02-group-system-repair-v1.0.0/native-input.json"
PARENT_SHA = "a93765916f45295da8a105434f032617bbead1668219e7718e3b74b8820b3f92"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E12.var02 BASE-GRP SystemRepair with 3.5-hour missions at two bases"
    )
    mission = table(doc, "MissionType")
    names = [c["name"] for c in mission["columns"]]
    rows = mission["instances"][0]["rows"]
    assert len(rows) == 1 and rows[0][names.index("MTID")] == "BASIC-MISSION" and rows[0][names.index("DURN")] == 2.0
    rows[0][names.index("DURN")] = 3.5
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
