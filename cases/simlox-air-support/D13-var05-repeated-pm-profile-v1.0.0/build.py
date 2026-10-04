"""Freeze flat and nested repeated PM activation from accepted D13.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D13-var01-pm-activation-v1.0.0/native-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "f4fce5c8f362be817264544f22f271c1ee47b6e635e871619525fa1c8545ca70"


def table(document, name):
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def set_cell(document, name, column, expected, value):
    t = table(document, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    index = [c["name"] for c in t["columns"]].index(column)
    row = t["instances"][0]["rows"][0]
    assert row[index] == expected, (name, column, row[index])
    row[index] = value


def limit(profile: str, start: float, end: float, enabled: str):
    return [profile, "<LIMIT>", start, end, 1, 0.0, enabled, "Y", None]


flat = []
for cycle in range(5):
    start = cycle * 12.0
    flat += [limit("PM-FLAT", start, start + 6.0, "N"),
             limit("PM-FLAT", start + 6.0, start + 12.0, "Y")]
nested = [
    ["PM-ROOT", "PM-HALF", 0.0, None, 5, 12.0, None, None, None],
    limit("PM-HALF", 0.0, 6.0, "N"),
    limit("PM-HALF", 6.0, 12.0, "Y"),
]

for arm, profile, rows in (("flat", "PM-FLAT", flat), ("nested", "PM-ROOT", nested)):
    document = json.loads(parent.read_text(encoding="utf-8"))
    assert len(document["model"]["tables"]) == 33
    set_cell(document, "ProblemDescription", "PDESC", "D13.var01 CAL24 PM disabled until hour 30 then enabled", f"D13.var05 {arm} repeated 12-hour PM activation")
    set_cell(document, "PMActivation", "PRID", "PM-SWITCH", profile)
    profile_table = table(document, "PMActivationProfile")
    assert len(profile_table["instances"]) == 1 and len(profile_table["instances"][0]["rows"]) == 2
    profile_table["instances"][0]["rows"] = rows
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == payload, f"frozen {arm} input changed"
    else:
        target.write_bytes(payload)
    print(arm, hashlib.sha256(payload).hexdigest())
