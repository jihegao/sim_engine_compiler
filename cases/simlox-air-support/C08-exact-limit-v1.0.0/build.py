"""Derive one exact-limit completion probe from the accepted C08 MAXUT case."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C08-shift-maxut-v1.0.0" / "maxut-one-input.json"
PARENT_SHA256 = "00e660275ace4d71d41cdafa725da2b552baeea9604756d94ad6b07de846e9d5"


def build() -> dict:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert description == ["C08 shift MAXUT one hour per crew; DRAOS=N"]
    description[0] = "C08 exact MAXUT limit at preparation completion; DRAOS=N"
    breakdown = tables["TaskBreakDown"]["instances"][0]["rows"][0]
    assert breakdown == ["PREP-FIXED", 1, "INSPECT", 2.0, None, None]
    breakdown[3] = 1.0
    assert tables["MissionPreparation"]["instances"][0]["rows"][0][3] == 2.0
    assert tables["ShiftResource"]["instances"][0]["rows"][0] == ["DAY-OPEN", "BASE-01", "P-CREW", 2, 1.0, None]
    return doc


def main() -> None:
    path = HERE / "exact-limit-input.json"
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw, "frozen C08 source differs"
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
