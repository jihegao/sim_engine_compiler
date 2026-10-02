"""Verify both G03.var04 inputs as exact parent-table deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import ARMS, HERE, PARENT, PARENT_SHA

DIFF = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("parent changed")
    before = tables(PARENT)
    arms = {}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        after = tables(path)
        if before.keys() != after.keys():
            raise ValueError("table set changed")
        changed = sorted(n for n in after if after[n] != before[n])
        if changed != ["ProblemDescription", "System", "SystemDeployment", "SystemRepair"]:
            raise ValueError((arm, changed))
        arms[arm] = {"input_sha256": sha(path),
                     "changed": {n: {"before": before[n], "after": after[n]} for n in changed}}
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G03",
              "variant_id": "G03.var04", "parent_sha256": PARENT_SHA, "arms": arms}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if DIFF.exists():
        if DIFF.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        DIFF.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(),
                      "arms": {arm: arms[arm]["input_sha256"] for arm in ARMS}}))


if __name__ == "__main__":
    main()
