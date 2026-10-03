"""Seal the exact h9-11 support gap to h11-12 overlap delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT, PARENT_SHA, build, sha

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    assert sha(PARENT) == PARENT_SHA
    before = {table["name"]: table for table in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {table["name"]: table for table in json.loads(build())["model"]["tables"]}
    assert set(before) == set(after)
    assert {name for name in before if before[name] != after[name]} == {"ProblemDescription", "TransportPolicyProfile"}
    old = before["TransportPolicyProfile"]["instances"][0]["rows"]
    new = after["TransportPolicyProfile"]["instances"][0]["rows"]
    cols = [col["name"] for col in before["TransportPolicyProfile"]["columns"]]
    assert old[1] == new[1] and len(old) == len(new) == 2
    changes = {cols[i]: [a, b] for i, (a, b) in enumerate(zip(old[0], new[0])) if a != b}
    assert changes == {"DURN": [9.0, 12.0]}
    return {"schema": "simlox-e10-var09-overlap-negative-exact-diff/v1", "parent_sha256": PARENT_SHA, "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": ["ProblemDescription", "TransportPolicyProfile"], "first_window_change": changes, "second_window_unchanged": new[1], "unchanged_parent_tables": len(before) - 2}


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
