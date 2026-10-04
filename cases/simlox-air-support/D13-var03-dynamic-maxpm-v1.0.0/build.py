"""Freeze paired time-varying MAXPM profiles from accepted static MAXPM=2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D13-var02-maxpm-two-v1.0.0/native-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "d65ba7873f89e9b8e391b731a04aaa9622b346b6f8fa7d4547e177b42a285e41"


def table(document, name):
    return next(t for t in document["model"]["tables"] if t["name"] == name)


def set_cell(document, name, column, expected, value):
    t = table(document, name)
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    index = [c["name"] for c in t["columns"]].index(column)
    row = t["instances"][0]["rows"][0]
    assert row[index] == expected, (name, column, row[index])
    row[index] = value


profile_columns = [
    {"datatype": "string", "key": True, "name": "PRID"},
    {"datatype": "string", "key": True, "name": "SPRID"},
    {"datatype": "double", "key": True, "name": "STIM"},
    {"datatype": "double", "name": "ETIM"},
    {"datatype": "integer", "name": "IQTY"},
    {"datatype": "double", "name": "IINT"},
    {"datatype": "integer", "name": "MAXPM"},
    {"datatype": "string", "name": "NOTE"},
]

for arm, last_limit in (("rise", 2), ("hold", 1)):
    document = json.loads(parent.read_text(encoding="utf-8"))
    assert len(document["model"]["tables"]) == 31
    set_cell(document, "ProblemDescription", "PDESC", "D13.var02 two calendar-PM aircraft, MAXPM two", f"D13.var03 MaxPMProfile 0-1-{last_limit}")
    set_cell(document, "Unit", "MAXPM", 2, 0)
    set_cell(document, "Unit", "MAXPMP", None, "CAP24")
    document["model"]["tables"].append({
        "columns": profile_columns,
        "instances": [{"instance_name": "", "rows": [
            ["CAP24", "<LIMIT>", 0.0, 24.25, 1, 0.0, 0, None],
            ["CAP24", "<LIMIT>", 24.25, 24.75, 1, 0.0, 1, None],
            ["CAP24", "<LIMIT>", 24.75, 36.0, 1, 0.0, last_limit, None],
        ]}],
        "name": "MaxPMProfile",
    })
    payload = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == payload, f"frozen {arm} input changed"
    else:
        target.write_bytes(payload)
    print(arm, hashlib.sha256(payload).hexdigest())
