"""Freeze exact accepted-position-FM to whole-aircraft attrition delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, ATTRITION_REFERENCE, ATTRITION_REFERENCE_SHA


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    result = {item["name"]: item for item in items}
    assert len(result) == len(items)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    control_raw = (HERE / "control-input.json").read_bytes()
    child_raw = (HERE / "attrition-input.json").read_bytes()
    assert sha(parent_raw) == PARENT_SHA and parent_raw == control_raw
    assert sha(ATTRITION_REFERENCE.read_bytes()) == ATTRITION_REFERENCE_SHA
    parent, child = tables(parent_raw), tables(child_raw)
    added = {name: child[name] for name in child.keys() - parent.keys()}
    removed = {name: parent[name] for name in parent.keys() - child.keys()}
    changed = {name: {"before": parent[name], "after": child[name]}
               for name in parent if name in child and parent[name] != child[name]}
    assert set(added) == {"DamageItem"} and not removed
    assert set(changed) == {"DamageType", "DamageFailureMode", "ProblemDescription"}
    result = {"schema": "simlox-h03-var03-attrition-exact-diff/v1",
              "parent_sha256": sha(parent_raw), "control_sha256": sha(control_raw),
              "attrition_sha256": sha(child_raw), "reference_sha256": ATTRITION_REFERENCE_SHA,
              "added_tables": added, "removed_tables": removed,
              "changed_tables": changed, "unchanged_table_count": len(parent) - len(changed)}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": sha(raw), "added_tables": list(added),
                      "changed_tables": list(changed)}))


if __name__ == "__main__":
    main()
