"""Freeze parent-to-explicit and explicit-to-fallback table deltas."""
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
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = sorted(name for name in before if name in after and before[name] != after[name])
    return {"added_tables": added, "removed_tables": removed,
            "changed_tables": {name: {"before": before[name], "after": after[name]}
                               for name in changed},
            "unchanged_table_count": len(before) - len(changed)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw_parent = PARENT.read_bytes()
    raw_explicit = (HERE / "explicit-input.json").read_bytes()
    raw_fallback = (HERE / "fallback-input.json").read_bytes()
    assert sha(raw_parent) == PARENT_SHA
    parent, explicit, fallback = map(tables, (raw_parent, raw_explicit, raw_fallback))
    first = delta(parent, explicit)
    second = delta(explicit, fallback)
    assert (not first["added_tables"] and not first["removed_tables"] and
            set(first["changed_tables"]) == {"ItemReplacement", "ProblemDescription"})
    assert (not second["added_tables"] and not second["removed_tables"] and
            set(second["changed_tables"]) == {"DamageReplacement", "ProblemDescription"})
    result = {"schema": "simlox-h02-var04-item-damage-replacement-fallback-exact-diff/v1",
              "parent_sha256": sha(raw_parent), "explicit_sha256": sha(raw_explicit),
              "fallback_sha256": sha(raw_fallback),
              "parent_to_explicit": first, "explicit_to_fallback": second}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": sha(raw), "first": list(first["changed_tables"]),
                      "second": list(second["changed_tables"])}))


if __name__ == "__main__":
    main()
