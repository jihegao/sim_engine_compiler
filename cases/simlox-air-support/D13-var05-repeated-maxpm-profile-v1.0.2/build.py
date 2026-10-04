"""Freeze flat and directly repeated MAXPM limits from accepted D13.var03."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D13-var03-dynamic-maxpm-v1.0.0/rise-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "3e9a0c1f79eb57ed0eeb054649e4d991e41e33d55eca3ee365c4df7260eb65f1"


def table(document, name):
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def set_cell(document, name, column, expected, value):
    t = table(document, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    index = [c["name"] for c in t["columns"]].index(column)
    row = t["instances"][0]["rows"][0]
    assert row[index] == expected, (name, column, row[index])
    row[index] = value


def limit(profile: str, start: float, end: float, capacity: int):
    return [profile, "<LIMIT>", start, end, 1, 0.0, capacity, None]


flat = []
for cycle in range(3):
    start = cycle * 12.0
    flat += [limit("CAP-FLAT", start, start + 0.25, 0),
             limit("CAP-FLAT", start + 0.25, start + 0.75, 1),
             limit("CAP-FLAT", start + 0.75, start + 12.0, 2)]
repeated = [
    ["CAP-REPEAT", "<LIMIT>", 0.0, 0.25, 3, 12.0, 0, None],
    ["CAP-REPEAT", "<LIMIT>", 0.25, 0.75, 3, 12.0, 1, None],
    ["CAP-REPEAT", "<LIMIT>", 0.75, 12.0, 3, 12.0, 2, None],
]

for arm, profile, rows in (("flat", "CAP-FLAT", flat), ("nested", "CAP-REPEAT", repeated)):
    document = json.loads(parent.read_text(encoding="utf-8"))
    assert len(document["model"]["tables"]) == 32
    set_cell(document, "ProblemDescription", "PDESC", "D13.var03 MaxPMProfile 0-1-2", f"D13.var05 {arm} repeated 12-hour MAXPM profile")
    set_cell(document, "Unit", "MAXPMP", "CAP24", profile)
    profile_table = table(document, "MaxPMProfile")
    assert len(profile_table["instances"]) == 1 and len(profile_table["instances"][0]["rows"]) == 3
    profile_table["instances"][0]["rows"] = rows
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == payload, f"frozen {arm} input changed"
    else:
        target.write_bytes(payload)
    print(arm, hashlib.sha256(payload).hexdigest())
