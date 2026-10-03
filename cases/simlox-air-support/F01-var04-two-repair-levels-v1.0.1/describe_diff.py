"""Verify the exact F01.var04 delta from accepted local three-level repair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "F01-var01-two-three-level-v1.0.1/three-level-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "exact-diff.json"
EXPECTED = ["ProblemDescription", "Station", "StationStructure", "ItemRepair",
            "Tasks", "StockAllocation", "TaskCategory", "TaskLevel", "MaintenanceAllocation"]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build() -> dict:
    left = json.loads(PARENT.read_text(encoding="utf-8"))["model"]["tables"]
    right = json.loads(CHILD.read_text(encoding="utf-8"))["model"]["tables"]
    a = {t["name"]: t for t in left}
    b = {t["name"]: t for t in right}
    if len(a) != len(left) or len(b) != len(right):
        raise ValueError("duplicate table")
    if list(b) != list(a) + ["TaskCategory", "TaskLevel", "MaintenanceAllocation"]:
        raise ValueError("unexpected table topology")
    changed = []
    for name in b:
        if name in a and a[name]["columns"] != b[name]["columns"]:
            raise ValueError(f"schema change: {name}")
        before = a[name]["instances"][0]["rows"] if name in a else []
        after = b[name]["instances"][0]["rows"]
        if before != after:
            changed.append({"table": name, "before_rows": before, "after_rows": after})
    if [d["table"] for d in changed] != EXPECTED:
        raise ValueError("unexpected changed tables")
    return {"schema": "simlox-f01-var04-two-repair-levels-exact-diff/v1",
            "parent_sha256": sha(PARENT), "input_sha256": sha(CHILD),
            "changed_tables": changed, "unchanged_existing_tables": len(a) - (len(changed) - 3)}


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        if OUT.read_bytes() != raw:
            raise ValueError("frozen delta differs")
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "changed_tables": EXPECTED}))


if __name__ == "__main__":
    main()
