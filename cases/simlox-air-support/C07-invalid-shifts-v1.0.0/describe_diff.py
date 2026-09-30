"""Verify each C07.var05 candidate changes only the intended business table."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA256, REPEATED_PARENT, REPEATED_PARENT_SHA256, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    assert sha(PARENT) == PARENT_SHA256 and sha(REPEATED_PARENT) == REPEATED_PARENT_SHA256
    parents = {"explicit": tables(PARENT), "repeated": tables(REPEATED_PARENT)}
    result = {"schema": "simlox-c07-invalid-shifts-exact-diff/v1",
              "parent_sha256": {"explicit": PARENT_SHA256, "repeated": REPEATED_PARENT_SHA256}, "variants": {}}
    for variant in VARIANTS:
        parent_name = "repeated" if variant == "repeated-overlap" else "explicit"
        before = parents[parent_name]
        path = HERE / f"{variant}-input.json"
        after = tables(path)
        assert before.keys() == after.keys()
        changed = sorted(k for k in before if before[k] != after[k])
        expected = ["ProblemDescription", "ShiftResource"] if variant == "over-capacity" else ["ProblemDescription", "ShiftProfile"]
        assert changed == expected, (variant, changed)
        result["variants"][variant] = {"parent": parent_name, "sha256": sha(path), "changed_tables": changed}
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
