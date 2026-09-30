"""Seal and constrain table-level deltas for the A14.var03 candidate."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, TURNROUND_DONOR, TURNROUND_DONOR_SHA, DEPENDENCE_DONOR, DEPENDENCE_DONOR_SHA, VARIANTS, build


def tabs(doc: dict) -> dict[str, dict]:
    result = {t["name"]: t for t in doc["model"]["tables"]}
    if len(result) != len(doc["model"]["tables"]):
        raise ValueError("duplicate table")
    return result


def changed(left: dict, right: dict) -> set[str]:
    return {n for n in left.keys() | right.keys() if left.get(n) != right.get(n)}


def main() -> None:
    if hashlib.sha256(PARENT.read_bytes()).hexdigest() != PARENT_SHA:
        raise ValueError("parent fingerprint changed")
    if hashlib.sha256(TURNROUND_DONOR.read_bytes()).hexdigest() != TURNROUND_DONOR_SHA:
        raise ValueError("turnround donor fingerprint changed")
    if hashlib.sha256(DEPENDENCE_DONOR.read_bytes()).hexdigest() != DEPENDENCE_DONOR_SHA:
        raise ValueError("dependence donor fingerprint changed")
    parent = tabs(json.loads(PARENT.read_bytes()))
    sources = {}
    for name in VARIANTS:
        raw = (HERE / f"{name}-input.json").read_bytes()
        doc = json.loads(raw)
        if doc != build(name):
            raise ValueError(f"builder/source mismatch: {name}")
        sources[name] = tabs(doc)
        expected = {"ProblemDescription", "MissionType", "MissionTurnround"}
        if name.startswith("regenerative"):
            expected.add("OperationProfile")
        if name.endswith("zero") or name.endswith("tolerant"):
            expected.add("MissionDependence")
        if changed(parent, sources[name]) != expected:
            raise ValueError(f"parent delta differs: {name}, {changed(parent, sources[name])}")
    contrasts = {
        "regenerative-control:regenerative-zero": {"ProblemDescription", "MissionDependence"},
        "regenerative-zero:regenerative-tolerant": {"ProblemDescription", "MissionDependence"},
        "regenerative-control:fixed-control": {"ProblemDescription", "OperationProfile"},
        "fixed-control:fixed-tolerant": {"ProblemDescription", "MissionDependence"},
    }
    for key, expected in contrasts.items():
        left, right = key.split(":")
        if changed(sources[left], sources[right]) != expected:
            raise ValueError(f"contrast delta differs: {key}")
    result = {
        "schema": "simlox-a14-var03-exact-table-diff/v1",
        "parent_sha256": PARENT_SHA,
        "turnround_donor_sha256": TURNROUND_DONOR_SHA,
        "dependence_donor_sha256": DEPENDENCE_DONOR_SHA,
        "variants": {},
        "contrasts": {},
    }
    for name in VARIANTS:
        source = sources[name]
        result["variants"][name] = {
            "input_sha256": hashlib.sha256((HERE / f"{name}-input.json").read_bytes()).hexdigest(),
            "changed_tables": {n: {"before": parent[n]["instances"] if n in parent else None,
                                   "after": source[n]["instances"] if n in source else None}
                               for n in sorted(changed(parent, source))},
            "unchanged_tables": sorted(parent.keys() & source.keys() - changed(parent, source)),
        }
    for key in contrasts:
        left, right = key.split(":")
        result["contrasts"][key] = sorted(changed(sources[left], sources[right]))
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
