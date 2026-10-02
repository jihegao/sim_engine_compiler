"""Draft four-arm crossed-category maintenance POINT matrix."""
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


def build() -> dict[str, dict]:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA, "station source parent changed"
    common = json.loads(raw)
    assert rows(common, "TaskCategory") == [["LRU-CM", "LRU corrective maintenance", None]]
    assert rows(common, "MaintenanceAllocation") == [
        ["AIR_BASIC", "LRU-CM", "BASE", "BASE-01", None],
        ["AIR_DEPOT", "LRU-CM", "BASE", "DEPOT-01", None]]
    assert len(rows(common, "ItemRepair")) == 2
    assert all(r[11] == "I01-LRU-DIRP" for r in rows(common, "ItemRepair"))
    rows(common, "TaskCategory").append(["DECOY-CM", "Alternative corrective maintenance", None])
    task_a = [row for row in rows(common, "Tasks") if row[0] == "I01-LRU-DIRP"]
    assert len(task_a) == 1 and task_a[0][2:] == ["LRU-CM", "BASE", None]
    task_a[0][1] = "Category task"
    rows(common, "Tasks").append(
        ["I01-CATEGORY-B", "Category task", "DECOY-CM", "BASE", None])
    rows(common, "MaintenanceAllocation").extend([
        ["AIR_BASIC", "DECOY-CM", "BASE", "DEPOT-01", None],
        ["AIR_DEPOT", "DECOY-CM", "BASE", "BASE-01", None]])
    result = {}
    for layer in ("real", "alternate"):
        source = copy.deepcopy(common)
        if layer == "alternate":
            for row in rows(source, "Tasks"):
                if row[0] == "I01-LRU-DIRP":
                    row[2] = "DECOY-CM"
                elif row[0] == "I01-CATEGORY-B":
                    row[2] = "LRU-CM"
        for apid, point in (("basic", "AIR_BASIC"), ("depot", "AIR_DEPOT")):
            doc = copy.deepcopy(source)
            rows(doc, "Control")[0][3] = point
            rows(doc, "ProblemDescription")[0][0] = (
                f"I01.var03 category matrix {layer} task at {point}")
            result[f"{apid}-{layer}"] = doc
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
