"""Derive an unreferenced item-repair candidate from restricted I01.var05."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I01-var05-none-maintenance-v1.0.0/none-input.json"
PARENT_SHA = "7dffc0b82a406761f55e1171491dfe9759c22c0123e2397aae4d19d6af7ba286"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def rows(doc: dict, name: str) -> list[list]:
    tables = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(tables) == 1 and len(tables[0]["instances"]) == 1
    return tables[0]["instances"][0]["rows"]


def main() -> None:
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA
    referenced = json.loads(raw)
    assert rows(referenced, "Control")[0][3] == "AIR_NONE"
    assert rows(referenced, "ItemRepair") == [[
        "TEACH-LRU-01", "BASE-01", 1.0, 0.0, 1.0, 1.0,
        None, None, None, None, None, "I01-LRU-DIRP", None, None, None, None
    ]]
    assert [r[:4] for r in rows(referenced, "MaintenanceAllocation")] == [
        ["AIR_BASIC", "LRU-CM", "BASE", "BASE-01"],
        ["AIR_NONE", "LRU-CM", "BASE", "<NONE>"],
    ]
    unreferenced = copy.deepcopy(referenced)
    rows(unreferenced, "ItemRepair")[0][11] = None
    rows(unreferenced, "ProblemDescription")[0][0] = (
        "I01.var04 unreferenced LRU direct repair under AIR_NONE")
    candidates = {
        "referenced-input.json": raw,
        "unreferenced-input.json": (json.dumps(unreferenced, ensure_ascii=False, indent=2) + "\n").encode(),
    }
    for name, data in candidates.items():
        out = HERE / name
        if out.exists() and out.read_bytes() != data:
            raise ValueError(f"frozen candidate differs: {name}")
        if not out.exists():
            out.write_bytes(data)
        print(name, sha(data))


if __name__ == "__main__":
    main()
