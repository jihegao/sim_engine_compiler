"""Freeze two installed LRUs and eight preselected half-probability seeds."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H02-var01-primary-lru-damage-v1.0.0/lru-input.json"
PARENT_SHA = "82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92"
QTY_REFERENCE = HERE.parent / "G01-var05-qty-two-v1.0.0/native-input.json"
QTY_REFERENCE_SHA = "ef21268a1f4c024e0c5bea24136509446e356ea3214dedd694c67825f376f984"
SEEDS = tuple(range(1, 9))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [item for item in doc["model"]["tables"] if item["name"] == name]
    assert len(found) == 1 and len(found[0]["instances"]) == 1
    return found[0]


def rows(doc: dict, name: str) -> list[list]:
    return table(doc, name)["instances"][0]["rows"]


def main() -> None:
    assert sha(PARENT) == PARENT_SHA and sha(QTY_REFERENCE) == QTY_REFERENCE_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    reference = json.loads(QTY_REFERENCE.read_text(encoding="utf-8-sig"))
    assert rows(reference, "ItemStructure")[0][:3] == ["TEACH-LRU-01", "TEACH-AIR-01", 2]
    assert rows(reference, "StockAllocation")[0][:4] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-01", 2]
    control = copy.deepcopy(parent)
    assert rows(control, "ItemStructure")[0][2] == rows(control, "StockAllocation")[0][3] == 1
    rows(control, "ItemStructure")[0][2] = 2
    rows(control, "StockAllocation")[0][3] = 2
    assert rows(control, "DamageItem")[0][:5] == ["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01", 1, 1]
    rows(control, "DamageItem")[0][3] = 0.0
    rows(control, "ProblemDescription")[0][0] = "H02.var02 two interchangeable LRUs, zero consequence control"
    outputs = {"control-input.json": control}
    for seed in SEEDS:
        child = copy.deepcopy(control)
        rows(child, "Control")[0][2] = str(seed)
        rows(child, "DamageItem")[0][3] = .5
        rows(child, "ProblemDescription")[0][0] = (
            f"H02.var02 two interchangeable LRUs, independent PROB0.5 consequence seed{seed}")
        outputs[f"seed-{seed}-input.json"] = child
    for name, doc in outputs.items():
        path = HERE / name
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists() and path.read_bytes() != raw:
            raise ValueError(f"frozen {name} differs")
        if not path.exists():
            path.write_bytes(raw)
        print(name, sha(path))


if __name__ == "__main__":
    main()
