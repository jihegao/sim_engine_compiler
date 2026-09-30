"""Freeze complete parent and pair differences for custom KM utilization."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, VARIANTS, build

ALLOWED_PARENT = {"ProblemDescription", "OperationParameter", "MissionTypeUtilization"}
ALLOWED_PAIR = {"ProblemDescription", "MissionTypeUtilization"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rows(document: dict) -> dict[str, dict]:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in document["model"]["tables"]}


def difference(left: dict, right: dict) -> dict[str, dict]:
    a, b = rows(left), rows(right)
    return {name: {"before": a.get(name), "after": b.get(name)} for name in sorted(set(a) | set(b)) if a.get(name) != b.get(name)}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    if sha(parent_raw) != PARENT_SHA:
        raise ValueError("accepted parent fingerprint differs")
    parent = json.loads(parent_raw)
    inputs, hashes = {}, {}
    for variant in VARIANTS:
        raw = (HERE / f"{variant}-input.json").read_bytes()
        document = json.loads(raw)
        if document != build(variant):
            raise ValueError(f"{variant} differs from builder")
        inputs[variant], hashes[variant] = document, sha(raw)
    parent_diffs = {variant: difference(parent, document) for variant, document in inputs.items()}
    if any(set(changes) != ALLOWED_PARENT for changes in parent_diffs.values()):
        raise ValueError("parent table delta differs from frozen design")
    pair = difference(inputs["per-hour"], inputs["per-mission"])
    if set(pair) != ALLOWED_PAIR:
        raise ValueError("pairwise delta differs from frozen design")
    result = {"schema": "simlox-a15-custom-utilization-v100-source-diff/v1", "parent_sha256": PARENT_SHA,
              "input_sha256": hashes, "parent_differences": parent_diffs, "pairwise_differences": pair}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists() and target.read_bytes() != data:
        raise ValueError("frozen exact diff differs")
    target.write_bytes(data)
    print(sha(data))


if __name__ == "__main__":
    main()
