"""Freeze exact source table differences from accepted C05 and between two resource-type capacities."""

from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, build

ALLOWED_PARENT = {"ProblemDescription", "Resource", "ResourceAllocation", "MissionResource"}
ALLOWED_PAIR = {"ProblemDescription", "ResourceAllocation"}


def table_map(doc: dict) -> dict:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in doc["model"]["tables"]}


def diff(a: dict, b: dict) -> dict:
    left, right = table_map(a), table_map(b)
    return {n: {"before": left.get(n), "after": right.get(n)} for n in sorted(set(left) | set(right)) if left.get(n) != right.get(n)}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    assert hashlib.sha256(parent_raw).hexdigest() == PARENT_SHA256
    parent = json.loads(parent_raw)
    docs = {}
    hashes = {}
    for capacity in (2, 0):
        raw = (HERE / f"radio-{capacity}-input.json").read_bytes()
        doc = json.loads(raw)
        assert doc == build(capacity)
        docs[capacity], hashes[str(capacity)] = doc, hashlib.sha256(raw).hexdigest()
    parent_diffs = {str(c): diff(parent, docs[c]) for c in docs}
    assert all(set(d) == ALLOWED_PARENT for d in parent_diffs.values())
    pair_diffs = {f"{a}-to-{b}": diff(docs[a], docs[b]) for a, b in ((2, 0),)}
    assert all(set(d) == ALLOWED_PAIR for d in pair_diffs.values())
    result = {"schema": "simlox-c05-var02-two-resource-types-source-diff/v1", "parent_sha256": PARENT_SHA256, "input_sha256": hashes, "parent_differences": parent_diffs, "pairwise_differences": pair_diffs}
    payload = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == payload
    else:
        target.write_bytes(payload)
    print(hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    main()
