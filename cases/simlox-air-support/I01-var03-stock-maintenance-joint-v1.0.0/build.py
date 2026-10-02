"""Freeze a four-POINT stock size by maintenance station diagnostic matrix."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var03-maintenance-station-v1.0.0/base-input.json"
PARENT_SHA = "4e16325638ff7aafcf47306101b42a780c02b06f957c0036317e300eb63abf72"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(doc: dict, name: str) -> list[list]:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]["instances"][0]["rows"]


POINTS = {
    "one-base": "AIR_BASIC",
    "one-depot": "AIR_DEPOT",
    "two-base": "AIR_TWO_BASE",
    "two-depot": "AIR_TWO_DEPOT",
}


def build() -> dict[str, dict]:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA, "station source parent changed"
    common = json.loads(raw)
    assert rows(common, "StockAllocation") == [
        [point, "TEACH-LRU-01", station, size, None, None, None, None, None]
        for point in ("AIR_BASIC", "AIR_DEPOT")
        for station, size in (("BASE-01", 1), ("DEPOT-01", 0))]
    assert rows(common, "MaintenanceAllocation") == [
        ["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
        ["AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01", None]]
    assert all(row[11] == "I01-LRU-DIRP" for row in rows(common, "ItemRepair"))
    assert rows(common, "ItemReorder") == []
    assert rows(common, "ResourceAllocation") == []
    for point in ("AIR_TWO_BASE", "AIR_TWO_DEPOT"):
        rows(common, "StockAllocation").extend([
            [point, "TEACH-LRU-01", "BASE-01", 2, None, None, None, None, None],
            [point, "TEACH-LRU-01", "DEPOT-01", 0, None, None, None, None, None]])
    rows(common, "MaintenanceAllocation").extend([
        ["AIR_TWO_BASE", "LRU-CM", "BASE", "BASE-01", None],
        ["AIR_TWO_DEPOT", "LRU-CM", "BASE", "DEPOT-01", None]])
    result = {}
    for arm, point in POINTS.items():
        doc = copy.deepcopy(common)
        rows(doc, "Control")[0][3] = point
        rows(doc, "ProblemDescription")[0][0] = (
            f"I01.var03 joint stock and maintenance POINT diagnostic {arm}")
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
