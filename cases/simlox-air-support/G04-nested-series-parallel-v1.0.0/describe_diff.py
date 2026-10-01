"""Freeze all parent-to-nested and paired-topology table differences."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, ARMS, build

ALLOWED = {"ProblemDescription", "FailureMode", "CMLocation", "MaterielOperationalModes", "RBDParallel",
           "RBDParallelStructure", "RBDSeries", "RBDSeriesStructure"}
PAIRED = ALLOWED - {"FailureMode", "CMLocation"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tables(document: dict) -> dict:
    items = document["model"]["tables"]
    assert len({item["name"] for item in items}) == len(items)
    return {item["name"]: item for item in items}


def difference(before: dict, after: dict) -> dict:
    old, new = tables(before), tables(after)
    assert not set(old) - set(new), "table removed"
    result = {}
    for name in sorted(set(old) | set(new)):
        a, b = old.get(name), new.get(name)
        if a == b:
            continue
        if a is not None:
            assert a["columns"] == b["columns"], f"schema changed: {name}"
        result[name] = {"before": None if a is None else a["instances"][0]["rows"],
                        "after": b["instances"][0]["rows"],
                        "columns": b["columns"] if a is None else None}
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    parent = json.loads(parent_raw)
    sources, changes = {}, {}
    for arm in ARMS:
        raw = (HERE / f"{arm}-input.json").read_bytes()
        document = json.loads(raw)
        assert document == build(arm)
        sources[arm] = sha(raw)
        changes[arm] = difference(parent, document)
        assert set(changes[arm]) == ALLOWED, (arm, sorted(changes[arm]))
    paired = difference(json.loads((HERE / "or-input.json").read_bytes()),
                        json.loads((HERE / "and-input.json").read_bytes()))
    assert set(paired) == PAIRED, sorted(paired)
    result = {"schema": "simlox-g04-nested-series-parallel-exact-diff/v1",
              "parent_sha256": PARENT_SHA256, "source_sha256": sources,
              "parent_to_arm": changes, "or_to_and": paired}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if args.write:
        if target.exists():
            raise FileExistsError(target)
        target.write_bytes(data)
    elif target.read_bytes() != data:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"parent_changed_tables": len(ALLOWED), "paired_changed_tables": len(PAIRED),
                      "sha256": sha(data)}))


if __name__ == "__main__":
    main()
