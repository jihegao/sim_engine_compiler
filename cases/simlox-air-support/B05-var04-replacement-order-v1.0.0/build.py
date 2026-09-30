"""Freeze reversed native replacement subtask order against published E01."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0" / "native-input.json"
PARENT_SHA = "84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931"
INPUT = HERE / "native-input.json"


def table(doc: dict, name: str) -> dict:
    return next(t for t in doc["model"]["tables"] if t["name"] == name)


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA:
        raise ValueError("published E01 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = "B05.var04 invalid replacement sequence: REPLACE before REMOVE"
    breakdown = table(doc, "TaskBreakDown")
    fields = [c["name"] for c in breakdown["columns"]]
    rows = breakdown["instances"][0]["rows"]
    if len(rows) != 2 or [r[fields.index("SUTID")] for r in rows] != ["<REMOVE>", "<REPLACE>"]:
        raise ValueError("E01 replacement order differs")
    first_type, first_duration = rows[0][fields.index("SUTID")], rows[0][fields.index("DURN")]
    second_type, second_duration = rows[1][fields.index("SUTID")], rows[1][fields.index("DURN")]
    rows[0][fields.index("SUTID")], rows[0][fields.index("DURN")] = second_type, second_duration
    rows[1][fields.index("SUTID")], rows[1][fields.index("DURN")] = first_type, first_duration
    return doc


def main() -> None:
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if INPUT.exists() and INPUT.read_bytes() != data:
        raise ValueError("frozen input differs")
    INPUT.write_bytes(data)
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
