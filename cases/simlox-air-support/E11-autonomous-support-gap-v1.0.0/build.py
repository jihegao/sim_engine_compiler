"""Freeze one E10.var03 support gap as an autonomous station candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E10-var03-ondem-support-gap-v1.0.0/native-input.json"
PARENT_SHA = "c79475655e9b0e0e2e5bd4aa412148b2044cb662521d95824b2276586ad712e8"


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build() -> bytes:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "E11 base E10.var03 support gap; BASE-01 AUTOM, bidirectional policy"
    )
    station = table(doc, "Station")
    names = [c["name"] for c in station["columns"]]
    rows = station["instances"][0]["rows"]
    assert len(rows) == 2 and rows[0][names.index("STID")] == "BASE-01"
    assert rows[0][names.index("TYPE")] == "WS"
    rows[0][names.index("TYPE")] = "AUTOM"
    link = table(doc, "StationStructure")
    names = [c["name"] for c in link["columns"]]
    rows = link["instances"][0]["rows"]
    assert len(rows) == 1 and rows[0][names.index("PFRMS")] == "DOWN-POLICY"
    assert rows[0][names.index("PTOMS")] is None
    rows[0][names.index("PTOMS")] = "DOWN-POLICY"
    policy = table(doc, "TransportPolicyProfile")["instances"][0]["rows"]
    assert [(r[1], r[2], r[5]) for r in policy] == [
        ("ONDEM", 0.0, 9.0), ("ONDEM", 11.0, 25.0)
    ]
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    path = HERE / "native-input.json"
    raw = build()
    if write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    else:
        assert path.read_bytes() == raw
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
