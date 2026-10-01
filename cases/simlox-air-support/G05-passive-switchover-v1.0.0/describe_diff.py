"""Freeze and check complete G05 passive standby source and paired TSWOV delta."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA256, ARMS, build

ALLOWED = {"ProblemDescription", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_tables(document: dict) -> dict:
    tables = document["model"]["tables"]
    assert len({t["name"] for t in tables}) == len(tables)
    return {t["name"]: t for t in tables}


def difference(before: dict, after: dict) -> dict:
    a, b = canonical_tables(before), canonical_tables(after)
    assert a.keys() == b.keys(), "table set changed"
    return {name: {"before": a[name]["instances"][0]["rows"],
                   "after": b[name]["instances"][0]["rows"]}
            for name in sorted(a) if a[name] != b[name]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    parent = json.loads(parent_raw)
    sources = {}
    changes = {}
    for arm in ARMS:
        source = HERE / f"{arm}-input.json"
        raw = source.read_bytes()
        assert json.loads(raw) == build(arm), arm
        sources[arm] = sha(raw)
        changes[arm] = difference(parent, json.loads(raw))
        assert set(changes[arm]) == ALLOWED, (arm, set(changes[arm]))
    arm_delta = difference(json.loads((HERE / "zero-input.json").read_bytes()),
                           json.loads((HERE / "half-input.json").read_bytes()))
    assert set(arm_delta) == {"ProblemDescription", "RBDParallel"}, set(arm_delta)
    assert arm_delta["RBDParallel"]["before"][0][4] == 0.0
    assert arm_delta["RBDParallel"]["after"][0][4] == 0.5
    result = {"schema": "simlox-g05-passive-switchover-exact-diff/v1", "parent_sha256": PARENT_SHA256,
              "source_sha256": sources, "parent_to_arm": changes, "zero_to_half": arm_delta}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if args.write:
        if target.exists():
            raise FileExistsError(target)
        target.write_bytes(data)
    elif target.read_bytes() != data:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"changed_tables": len(ALLOWED), "arm_delta": sorted(arm_delta),
                      "sha256": sha(data)}))


if __name__ == "__main__":
    main()
