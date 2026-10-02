"""Freeze a four-POINT stock/resource/maintenance interaction diagnostic."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var03-stock-maintenance-joint-v1.0.0/one-base-input.json"
PARENT_SHA = "96dd5cb98a9e5847fc7ae0d4236d6214dbe1825fe5c89c9e87ad3c951621b049"
DONOR = HERE.parent / "I01-var01-resource-points-v1.0.0/selected-input.json"
DONOR_SHA = "ac35a07731c629e16ba6bd83183eaca9c244161c2cc05a07cf7b2127cd52bbc5"
POINTS = {"one-base": "AIR_BASIC", "one-depot": "AIR_DEPOT",
          "two-base": "AIR_TWO_BASE", "two-depot": "AIR_TWO_DEPOT"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def build() -> dict[str, dict]:
    parent_raw, donor_raw = PARENT.read_bytes(), DONOR.read_bytes()
    assert sha(parent_raw) == PARENT_SHA and sha(donor_raw) == DONOR_SHA
    common, donor = json.loads(parent_raw), json.loads(donor_raw)
    assert rows(common, "MissionPreparation") == [] and rows(common, "Resource") == []
    assert rows(common, "ResourceAllocation") == [] and rows(common, "SubTaskResource") == []
    assert rows(common, "SubTaskType") == []
    assert rows(donor, "MissionPreparation") == [
        ["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 0.75, "PREP-FIXED", None, None]]
    assert rows(donor, "SubTaskResource") == [
        ["PREP-FIXED", 1, "P-CREW", 2, 1, None, None, None, None]]
    for name in ("MissionPreparation", "Resource", "SubTaskResource", "SubTaskType"):
        assert table(common, name)["columns"] == table(donor, name)["columns"]
        rows(common, name).extend(copy.deepcopy(rows(donor, name)))
    assert table(common, "TaskBreakDown")["columns"] == table(donor, "TaskBreakDown")["columns"]
    assert table(common, "Tasks")["columns"] == table(donor, "Tasks")["columns"]
    assert rows(donor, "Tasks") == [
        ["PREP-FIXED", "Serial 10+20-minute BASIC-MISSION preparation", None, None, None]]
    rows(common, "Tasks").extend(copy.deepcopy(rows(donor, "Tasks")))
    rows(common, "TaskBreakDown").extend(copy.deepcopy(rows(donor, "TaskBreakDown")))
    assert table(common, "ResourceAllocation")["columns"] == table(donor, "ResourceAllocation")["columns"]
    for arm, point in POINTS.items():
        crew = 2 if arm.startswith("one") else 3
        rows(common, "ResourceAllocation").extend([
            [point, "P-CREW", "BASE-01", crew, None],
            [point, "P-OTHER", "BASE-01", 0, None]])
    result = {}
    for arm, point in POINTS.items():
        doc = copy.deepcopy(common)
        rows(doc, "Control")[0][3] = point
        rows(doc, "ProblemDescription")[0][0] = (
            f"I01.var03 three allocation POINT diagnostic {arm}")
        result[arm] = doc
    return result


def main() -> None:
    for arm, doc in build().items():
        name = f"{arm}-input.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        path = HERE / name
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen source differs: {name}")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(raw))


if __name__ == "__main__":
    main()
