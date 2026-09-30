"""Freeze exact parent-to-seed source differences for the RPROB-half matrix."""

from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, VARIANTS, build


def table_map(doc: dict) -> dict:
    return {t["name"]: {"columns": t["columns"], "instances": t["instances"]} for t in doc["model"]["tables"]}


def main() -> None:
    parent_raw = PARENT.read_bytes()
    assert hashlib.sha256(parent_raw).hexdigest() == PARENT_SHA256
    before = table_map(json.loads(parent_raw))
    differences, hashes = {}, {}
    for variant, seed in VARIANTS.items():
        raw = (HERE / f"{variant}-input.json").read_bytes()
        doc = json.loads(raw)
        assert doc == build(variant)
        after = table_map(doc)
        changes = {name: {"before": before.get(name), "after": after.get(name)} for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
        expected = {"ProblemDescription", "SubTaskResource"} | ({"Control"} if seed != 1 else set())
        assert set(changes) == expected, (variant, set(changes))
        differences[variant] = changes
        hashes[variant] = hashlib.sha256(raw).hexdigest()
    result = {"schema": "simlox-c06-rprob-half-matrix-source-diff/v1", "parent_sha256": PARENT_SHA256, "input_sha256": hashes, "parent_differences": differences}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == data
    else:
        target.write_bytes(data)
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
