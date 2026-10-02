"""Freeze accepted D06 parent to damage control and PROB0-to-1 child."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, DAMAGE_REFERENCE


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
    return {"added_tables": {name: after[name] for name in added},
            "removed_tables": removed,
            "changed_tables": {name: {"before": before[name], "after": after[name]}
                               for name in changed},
            "unchanged_table_count": len(before) - len(changed)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    control_raw = (HERE / "control-input.json").read_bytes()
    mode_raw = (HERE / "mode-input.json").read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    first = delta(tables(parent_raw), tables(control_raw))
    second = delta(tables(control_raw), tables(mode_raw))
    assert set(first["added_tables"]) == {"DamageType", "MissionDamage", "DamageFailureMode"}
    assert not first["removed_tables"] and set(first["changed_tables"]) == {"FailureMode", "ProblemDescription"}
    assert not second["added_tables"] and not second["removed_tables"]
    assert set(second["changed_tables"]) == {"DamageFailureMode", "ProblemDescription"}
    result = {"schema": "simlox-h03-var01-position-fm-damage-exact-diff/v1",
              "parent_sha256": sha(parent_raw), "damage_reference_sha256": sha(DAMAGE_REFERENCE.read_bytes()),
              "control_sha256": sha(control_raw), "mode_sha256": sha(mode_raw),
              "parent_to_control": first, "control_to_mode": second}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": sha(raw), "parent_to_control": list(first["added_tables"]),
                      "control_to_mode": list(second["changed_tables"])}))


if __name__ == "__main__":
    main()
