"""Verify exact table-level source delta for the frozen 48-hour gap candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, OUTPUT, PARENT, PARENT_SHA256


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    assert sha(PARENT) == PARENT_SHA256
    parent, child = tables(PARENT), tables(OUTPUT)
    assert parent.keys() == child.keys()
    changed = sorted(k for k in parent if parent[k] != child[k])
    assert changed == ["Control", "MissionType", "OperationProfile", "ProblemDescription", "ResultCollection", "ShiftProfile"]
    result = {"schema": "simlox-c07-long-gap-exact-diff/v1", "parent_sha256": PARENT_SHA256,
              "input_sha256": sha(OUTPUT), "changed_tables": changed}
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
