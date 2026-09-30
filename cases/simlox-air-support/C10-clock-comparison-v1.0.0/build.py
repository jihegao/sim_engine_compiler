"""Derive the calendar-clock child from the accepted operational C10 input."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C10-resource-failure-v1.0.0" / "oper-no-spare-input.json"
PARENT_SHA = "c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b"


def build() -> dict:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    child = json.loads(PARENT.read_bytes())
    tables = {table["name"]: table for table in child["model"]["tables"]}
    failure_row = tables["ResourceStationData"]["instances"][0]["rows"][0]
    assert failure_row == ["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, None, None]
    assert tables["ResourceAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]]
    failure_row[6] = "CALENDAR"
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = "C10 calendar-time resource failures; crew pool 2; seed 1"
    return child


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "calendar-two-crew-input.json"
    if path.exists():
        assert path.read_bytes() == raw, "frozen calendar child differs"
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
