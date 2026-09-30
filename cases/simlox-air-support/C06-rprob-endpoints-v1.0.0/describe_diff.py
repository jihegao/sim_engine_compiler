"""Freeze exact accepted-parent and endpoint-to-endpoint RPROB differences."""

from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, VARIANTS, build


def table_map(doc: dict) -> dict:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in doc["model"]["tables"]}


def diff(a: dict, b: dict) -> dict:
    left, right = table_map(a), table_map(b)
    return {name: {"before": left.get(name), "after": right.get(name)} for name in sorted(set(left) | set(right)) if left.get(name) != right.get(name)}


def main() -> None:
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    parent = json.loads(raw)
    docs, hashes = {}, {}
    for variant in VARIANTS:
        data = (HERE / f"{variant}-input.json").read_bytes()
        docs[variant] = json.loads(data)
        assert docs[variant] == build(variant)
        hashes[variant] = hashlib.sha256(data).hexdigest()
    parent_diffs = {variant: diff(parent, doc) for variant, doc in docs.items()}
    assert set(parent_diffs["rprob-0"]) == {"ProblemDescription", "SubTaskResource"}
    assert set(parent_diffs["rprob-1"]) == {"ProblemDescription"}
    pair = diff(docs["rprob-0"], docs["rprob-1"])
    assert set(pair) == {"ProblemDescription", "SubTaskResource"}
    result = {"schema": "simlox-c06-rprob-endpoints-source-diff/v1", "parent_sha256": PARENT_SHA256, "input_sha256": hashes, "parent_differences": parent_diffs, "pairwise_differences": pair}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == data
    else:
        target.write_bytes(data)
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
