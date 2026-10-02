"""Verify exact G03.var03 parent-to-child table delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, OUT, PARENT, PARENT_SHA

DIFF = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("parent changed")
    before, after = tables(PARENT), tables(OUT)
    if before.keys() != after.keys():
        raise ValueError("table set changed")
    changed = sorted(name for name in after if before[name] != after[name])
    if changed != ["Operations", "ProblemDescription", "SystemDeployment", "Unit"]:
        raise ValueError(changed)
    result = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "G03",
              "variant_id": "G03.var03", "parent_sha256": PARENT_SHA,
              "input_sha256": sha(OUT), "changed": {n: {"before": before[n], "after": after[n]} for n in changed}}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if DIFF.exists():
        if DIFF.read_bytes() != data:
            raise ValueError("frozen exact diff differs")
    else:
        DIFF.write_bytes(data)
    print(json.dumps({"diff_sha256": hashlib.sha256(data).hexdigest(), "changed_tables": changed}))


if __name__ == "__main__":
    main()
