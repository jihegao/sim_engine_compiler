"""Freeze D13 local PM criticality arms from the accepted MAXPM control."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
root = case.parent
parent = root / "D13-var02-maxpm-two-v1.0.0/native-input.json"
activation_source = root / "D13-var01-pm-activation-v1.0.0/native-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "d65ba7873f89e9b8e391b731a04aaa9622b346b6f8fa7d4547e177b42a285e41"
assert hashlib.sha256(activation_source.read_bytes()).hexdigest() == "f4fce5c8f362be817264544f22f271c1ee47b6e635e871619525fa1c8545ca70"


def table(document, name):
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def row(document, name):
    t = table(document, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    return dict(zip((c["name"] for c in t["columns"]), t["instances"][0]["rows"][0]))


def set_cell(document, name, column, expected, value):
    t = table(document, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    index = [c["name"] for c in t["columns"]].index(column)
    target = t["instances"][0]["rows"][0]
    assert target[index] == expected, (name, column, target[index])
    target[index] = value


template = json.loads(activation_source.read_text(encoding="utf-8"))
activation = copy.deepcopy(table(template, "PMActivation"))
assert row(template, "PMActivation") == {
    "USTID": "TEACH-UNIT", "PMID": "CAL24", "ENPM": "Y", "CRIT": "Y", "PRID": "PM-SWITCH", "NOTE": None
}

for arm in ("y", "n"):
    document = json.loads(parent.read_text(encoding="utf-8"))
    assert len(document["model"]["tables"]) == 31
    set_cell(document, "ProblemDescription", "PDESC", "D13.var02 two calendar-PM aircraft, MAXPM two", f"D13.var02/04 CRIT={arm.upper()} at MAXPM=0")
    set_cell(document, "Unit", "MAXPM", 2, 0)
    set_cell(document, "MaterielPM", "DTIM", 0.5, 0.1)
    record = copy.deepcopy(activation)
    values = record["instances"][0]["rows"][0]
    names = [c["name"] for c in record["columns"]]
    values[names.index("CRIT")] = arm.upper()
    values[names.index("PRID")] = None
    document["model"]["tables"].append(record)
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == payload, f"frozen {arm} input changed"
    else:
        target.write_bytes(payload)
    print(arm, hashlib.sha256(payload).hexdigest())
