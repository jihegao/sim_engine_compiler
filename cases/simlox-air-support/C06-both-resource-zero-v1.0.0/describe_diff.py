"""Freeze the exact accepted-C06 to both-zero source difference."""

from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, build


def table_map(doc: dict) -> dict:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in doc["model"]["tables"]}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    assert hashlib.sha256(parent_raw).hexdigest() == PARENT_SHA256
    child_raw = (HERE / "both-zero-input.json").read_bytes()
    child = json.loads(child_raw)
    assert child == build()
    left, right = table_map(json.loads(parent_raw)), table_map(child)
    changes = {name: {"before": left.get(name), "after": right.get(name)} for name in sorted(set(left) | set(right)) if left.get(name) != right.get(name)}
    assert set(changes) == {"ProblemDescription", "ResourceAllocation"}
    result = {"schema": "simlox-c06-both-resource-zero-source-diff/v1", "parent_sha256": PARENT_SHA256, "input_sha256": hashlib.sha256(child_raw).hexdigest(), "differences": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
