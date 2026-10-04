"""Freeze eight-aircraft, 43-day, no-failure F04.var01 source from accepted F03.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F03-var01-two-base-crew-v1.0.0" / "staffed-input.json"
PARENT_SHA = "4c01c6fd0c7f290c5af7032b4fa205ebbc6461c4c9917ccdaa7178dd9542bee9"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(doc: dict, name: str) -> list[list]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(matches) == 1 and len(matches[0]["instances"]) == 1
    return matches[0]["instances"][0]["rows"]


def build() -> dict:
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    doc = json.loads(parent_raw)
    assert len(doc["model"]["tables"]) == 32
    assert rows(doc, "Control")[0][:7] == [1, 60.0, "1", "AIR_BASIC", 0.5, 0, 60.0]
    assert [r[:3] for r in rows(doc, "SystemDeployment")] == [
        ["TEACH-AIR-01", "TEACH-UNIT", 2],
        ["TEACH-AIR-01", "TEACH-UNIT-2", 1]]
    assert [r[3] for r in rows(doc, "Item")] == [1000000.0, 1000000.0]
    assert rows(doc, "System")[0][3] == 1000000.0
    assert [r[:7] for r in rows(doc, "OperationProfile")] == [
        ["BASIC-SCHEDULE", "A09-DAILY-TWO-WAVE", 0.0, "SCHEDULED", 2, None, 48.0],
        ["A09-DAILY-TWO-WAVE", "RISK-MISSION", 21.5, "SCHEDULED", 1, None, 0],
        ["A09-DAILY-TWO-WAVE", "BASIC-MISSION", 24.75, "SCHEDULED", 1, None, 0],
        ["BASE2-SCHEDULE", "BASE2-MISSION", 8.0, "SCHEDULED", 1, None, 0]]
    assert all(r[13] == 0 for r in rows(doc, "MissionType"))
    rows(doc, "ProblemDescription")[0][0] = "F04.var01 v1.0.1 eight-aircraft 43-day deterministic two-base regression"
    control = rows(doc, "Control")[0]
    control[1] = control[6] = 1032.0
    for row in rows(doc, "ResultCollection"):
        assert row[3] == 60.0
        row[3] = 1032.0
    rows(doc, "SystemDeployment")[0][2] = 5
    rows(doc, "SystemDeployment")[1][2] = 3
    rows(doc, "System")[0][3] = 0.0
    for row in rows(doc, "Item"):
        row[3] = 0.0
    profiles = rows(doc, "OperationProfile")
    profiles[0][4] = 21
    profiles[0][6] = 1008.0
    profiles[3][4] = 21
    profiles[3][6] = 1008.0
    return doc


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "native-input.json"
    if target.exists():
        assert target.read_bytes() == raw, "frozen F04 input changed"
    else:
        target.write_bytes(raw)
    print(json.dumps({"accepted_parent_sha256": PARENT_SHA, "input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
