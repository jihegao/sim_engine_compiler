"""Derive one C08 MAXUT input from the accepted explicit C07 shift control."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
PARENT_SHA256 = "e585322b00f7697c2a4e37b5844ffb031b376fcf5756c52d0f146375f9d9a30e"


def build() -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {t["name"]: t for t in doc["model"]["tables"]}
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert description == ["C07 two equivalent crew shifts via explicit profile; DRAOS=N"]
    description[0] = "C08 shift MAXUT one hour per crew; DRAOS=N"
    row = tables["ShiftResource"]["instances"][0]["rows"][0]
    assert row == ["DAY-OPEN", "BASE-01", "P-CREW", 2, None, None]
    row[4] = 1.0
    assert tables["ResourceAllocation"]["instances"][0]["rows"][0][3] == 2
    return doc


def main() -> None:
    path = HERE / "maxut-one-input.json"
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw, "frozen C08 source differs"
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
