"""Freeze the A02-to-H01 and DAMP 0-to-1 authored-table deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, SOURCES, build


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table_map(document: dict) -> dict:
    tables = document["model"]["tables"]
    result = {t["name"]: t for t in tables}
    assert len(result) == len(tables)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    zero_raw, certain_raw = (SOURCES[arm].read_bytes() for arm in ("zero", "certain"))
    assert sha(parent_raw) == PARENT_SHA256
    assert json.loads(zero_raw) == build("zero") and json.loads(certain_raw) == build("certain")
    parent, zero, certain = (table_map(json.loads(raw)) for raw in
                             (parent_raw, zero_raw, certain_raw))
    added = sorted(set(zero) - set(parent))
    assert added == ["DamageItem", "DamageType", "MissionDamage"]
    assert set(parent) - set(zero) == set()
    parent_changes = sorted(name for name in parent if parent[name] != zero[name])
    assert parent_changes == ["ProblemDescription"]
    assert zero.keys() == certain.keys()
    paired = {name: {"before": zero[name]["instances"][0]["rows"],
                     "after": certain[name]["instances"][0]["rows"]}
              for name in sorted(zero) if zero[name] != certain[name]}
    assert set(paired) == {"MissionDamage", "ProblemDescription"}
    assert paired["MissionDamage"]["before"] == [
        ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 0.0, None, None]]
    assert paired["MissionDamage"]["after"] == [
        ["BASIC-MISSION", "TEACH-AIR-01", "BATTLE-LOSS", 1.0, None, None]]
    result = {
        "schema": "simlox-h01-var01-certain-attrition-exact-diff/v1",
        "parent_sha256": PARENT_SHA256,
        "zero_sha256": sha(zero_raw),
        "certain_sha256": sha(certain_raw),
        "parent_to_zero": {"added_tables": added, "changed_tables": parent_changes},
        "zero_to_certain": paired,
    }
    data = (json.dumps(result, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(data)
    elif output.read_bytes() != data:
        raise ValueError("frozen H01 diff differs")
    print(json.dumps({"added_tables": added, "pair_changed": sorted(paired),
                      "sha256": sha(data)}))


if __name__ == "__main__":
    main()
