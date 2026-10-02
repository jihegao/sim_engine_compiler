"""Freeze E01-to-two-POINT and APID-only child deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    result = {item["name"]: item for item in items}
    assert len(result) == len(items)
    return result


def delta(before: dict, after: dict) -> dict:
    return {"added_tables": {n: after[n] for n in after.keys() - before.keys()},
            "removed_tables": {n: before[n] for n in before.keys() - after.keys()},
            "changed_tables": {n: {"before": before[n], "after": after[n]}
                               for n in before if n in after and before[n] != after[n]},
            "unchanged_table_count": sum(before[n] == after[n] for n in before.keys() & after.keys())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    stocked_raw = (HERE / "stocked-input.json").read_bytes()
    empty_raw = (HERE / "empty-input.json").read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    p, s, e = (tables(raw) for raw in (parent_raw, stocked_raw, empty_raw))
    parent_to_stocked, stocked_to_empty = delta(p, s), delta(s, e)
    assert not parent_to_stocked["added_tables"] and not parent_to_stocked["removed_tables"]
    assert set(parent_to_stocked["changed_tables"]) == {"StockAllocation", "ProblemDescription"}
    assert not stocked_to_empty["added_tables"] and not stocked_to_empty["removed_tables"]
    assert set(stocked_to_empty["changed_tables"]) == {"Control", "ProblemDescription"}
    result = {"schema": "simlox-i01-var01-two-stock-points-exact-diff/v1",
              "parent_sha256": sha(parent_raw), "stocked_sha256": sha(stocked_raw),
              "empty_sha256": sha(empty_raw), "parent_to_stocked": parent_to_stocked,
              "stocked_to_empty": stocked_to_empty}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": sha(raw), "parent_changed": list(parent_to_stocked["changed_tables"]),
                      "APID_changed": list(stocked_to_empty["changed_tables"])}))


if __name__ == "__main__":
    main()
