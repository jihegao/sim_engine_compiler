"""Certify only the two appended J06 result-control tables."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, OUTPUT, build, sha


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before, after = json.loads(PARENT.read_bytes()), json.loads(OUTPUT.read_bytes())
    if sha(PARENT) != PARENT_SHA or after != build() or after["model"]["tables"][:-2] != before["model"]["tables"]:
        raise ValueError("frozen source or parent tables changed")
    result = {"schema": "simlox-j06-system-replication-exact-diff/v1", "parent_input_sha256": PARENT_SHA,
              "child_input_sha256": sha(OUTPUT), "unchanged_parent_tables": 32,
              "appended_tables": after["model"]["tables"][-2:], "other_changes": []}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(hashlib.sha256(raw).hexdigest())
