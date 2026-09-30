"""Rebuild the exact A13.var06 source-table delta from accepted A13."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {tab["name"]: tab for tab in json.loads(path.read_bytes())["model"]["tables"]}


def delta(before: dict, after: dict) -> dict:
    return {name: {"before": before.get(name), "after": after.get(name)}
            for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}


def main() -> None:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted parent changed")
    before = tables(PARENT)
    hashes = {}
    changes = {}
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        hashes[variant] = sha(path)
        changes[variant] = delta(before, tables(path))
        expected = {"ProblemDescription"}
        if variant != "fixed-fixed":
            expected.add("MissionType")
        if variant.endswith("control"):
            expected.add("MissionDependence")
        if set(changes[variant]) != expected:
            raise ValueError(f"unexpected {variant} table delta: {set(changes[variant])}")
    result = {"schema": "simlox-a13-var06-fixed-role-exact-diff/v1",
              "parent_sha256": PARENT_SHA, "inputs_sha256": hashes,
              "changed_tables": changes}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
