"""Check the exact accepted FIXED parent to empty-departure probe delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT, PARENT_SHA, build, sha

OUTPUT = HERE / "exact-diff.json"


def table_map(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def describe() -> dict:
    assert sha(PARENT) == PARENT_SHA
    before = table_map(json.loads(PARENT.read_text(encoding="utf-8-sig")))
    after = table_map(json.loads(build()))
    assert set(before) == set(after)
    assert {name for name in before if before[name] != after[name]} == {"ProblemDescription", "TransportPolicyProfile"}
    old_desc = before["ProblemDescription"]["instances"][0]["rows"]
    new_desc = after["ProblemDescription"]["instances"][0]["rows"]
    assert len(old_desc) == len(new_desc) == 1
    old_profile, new_profile = before["TransportPolicyProfile"], after["TransportPolicyProfile"]
    assert old_profile["columns"] == new_profile["columns"]
    old_rows = old_profile["instances"][0]["rows"]
    new_rows = new_profile["instances"][0]["rows"]
    assert len(old_rows) == 1 and len(new_rows) == 2
    assert old_rows[0] == new_rows[1]
    assert new_rows[0] == ["DOWN-POLICY", "FIXED", 8.0, 1, 0.0, None, 1, 2.0, None, None]
    assert new_rows[1] == ["DOWN-POLICY", "FIXED", 11.0, 1, 0.0, None, 1, 2.0, None, None]
    return {
        "schema": "simlox-e10-var02-empty-fixed-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "source_sha256": hashlib.sha256(build()).hexdigest(),
        "changed_tables": ["ProblemDescription", "TransportPolicyProfile"],
        "description_before": old_desc[0][0],
        "description_after": new_desc[0][0],
        "added_profile_row": new_rows[0],
        "unchanged_h11_profile_row": new_rows[1],
        "unchanged_parent_tables": len(before) - 2,
    }


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
