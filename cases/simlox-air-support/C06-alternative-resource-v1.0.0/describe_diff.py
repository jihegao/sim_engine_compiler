"""Freeze complete C03-to-C06 and controlled pair source differences."""

from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, VARIANTS, build

PARENT_TABLES = {"ProblemDescription", "MissionPreparation", "Tasks", "TaskBreakDown", "SubTaskResource", "Resource", "ResourceAllocation"}
PAIR_TABLES = {
    "primary-2-artf-2-to-primary-0-artf-2": {"ProblemDescription", "ResourceAllocation"},
    "primary-0-artf-1-to-primary-0-artf-2": {"ProblemDescription", "SubTaskResource"},
}


def table_map(doc: dict) -> dict:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in doc["model"]["tables"]}


def diff(a: dict, b: dict) -> dict:
    left, right = table_map(a), table_map(b)
    return {name: {"before": left.get(name), "after": right.get(name)} for name in sorted(set(left) | set(right)) if left.get(name) != right.get(name)}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    assert hashlib.sha256(parent_raw).hexdigest() == PARENT_SHA256
    parent = json.loads(parent_raw)
    docs = {}
    hashes = {}
    for variant in VARIANTS:
        raw = (HERE / f"{variant}-input.json").read_bytes()
        doc = json.loads(raw)
        assert doc == build(variant)
        docs[variant], hashes[variant] = doc, hashlib.sha256(raw).hexdigest()
    parent_diffs = {v: diff(parent, doc) for v, doc in docs.items()}
    assert all(set(changes) == PARENT_TABLES for changes in parent_diffs.values())
    pair_diffs = {}
    for label, allowed in PAIR_TABLES.items():
        a, b = label.split("-to-")
        changes = diff(docs[a], docs[b])
        assert set(changes) == allowed
        pair_diffs[label] = changes
    result = {"schema": "simlox-c06-alternative-resource-source-diff/v1", "parent_sha256": PARENT_SHA256, "input_sha256": hashes, "parent_differences": parent_diffs, "pairwise_differences": pair_diffs}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
