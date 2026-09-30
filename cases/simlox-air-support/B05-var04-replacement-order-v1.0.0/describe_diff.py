"""Freeze complete table difference from published E01 replacement parent."""
from __future__ import annotations

import hashlib
import json

from build import HERE, INPUT, PARENT, PARENT_SHA, build

ALLOWED = {"ProblemDescription", "TaskBreakDown"}


def rows(document: dict) -> dict[str, dict]:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in document["model"]["tables"]}


def main() -> None:
    parent_raw, child_raw = PARENT.read_bytes(), INPUT.read_bytes()
    if hashlib.sha256(parent_raw).hexdigest() != PARENT_SHA:
        raise ValueError("parent differs")
    parent, child = json.loads(parent_raw), json.loads(child_raw)
    if child != build():
        raise ValueError("child differs from builder")
    left, right = rows(parent), rows(child)
    delta = {name: {"before": left.get(name), "after": right.get(name)} for name in sorted(set(left) | set(right)) if left.get(name) != right.get(name)}
    if set(delta) != ALLOWED:
        raise ValueError(f"changed tables differ: {sorted(delta)}")
    result = {"schema": "simlox-b05-var04-replacement-order-v100-source-diff/v1", "parent_sha256": PARENT_SHA,
              "input_sha256": hashlib.sha256(child_raw).hexdigest(), "differences": delta}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists() and target.read_bytes() != data:
        raise ValueError("frozen diff differs")
    target.write_bytes(data)
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
