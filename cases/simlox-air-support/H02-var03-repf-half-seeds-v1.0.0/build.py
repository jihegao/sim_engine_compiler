"""Freeze eight preselected REPF0.5 seeds from accepted REPF1 parent."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var03-repf-zero-v1.0.0/repairable-input.json"
PARENT_SHA = "82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92"
SEEDS = tuple(range(1, 9))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row(doc: dict, name: str) -> list:
    found = [table for table in doc["model"]["tables"] if table["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    rows = found[0]["instances"][0]["rows"]
    assert len(rows) == 1
    return rows[0]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent = json.loads(PARENT.read_bytes())
    assert row(parent, "DamageItem") == [
        "BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1.0, 1.0, None, None]
    assert row(parent, "Control")[2] == "1"
    for seed in SEEDS:
        child = copy.deepcopy(parent)
        row(child, "DamageItem")[4] = .5
        row(child, "Control")[2] = str(seed)
        row(child, "ProblemDescription")[0] = f"H02.var03 primary LRU damage REPF half seed {seed}"
        raw = (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        path = HERE / f"seed-{seed}-input.json"
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen input differs: {path.name}")
        if not path.exists():
            path.write_bytes(raw)
        print(seed, sha(path))


if __name__ == "__main__":
    main()
