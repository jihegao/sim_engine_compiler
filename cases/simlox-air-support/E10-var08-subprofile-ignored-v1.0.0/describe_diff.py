"""Seal the exact accepted nested-repeat to ignored-wrapper delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT, PARENT_SHA, build, sha

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    assert sha(PARENT) == PARENT_SHA
    old = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    new = json.loads(build())
    before = {t["name"]: t for t in old["model"]["tables"]}
    after = {t["name"]: t for t in new["model"]["tables"]}
    assert set(before) == set(after)
    assert {k for k in before if before[k] != after[k]} == {"ProblemDescription", "TransportPolicyProfile"}
    old_profile, new_profile = before["TransportPolicyProfile"], after["TransportPolicyProfile"]
    assert old_profile["columns"] == new_profile["columns"]
    old_rows = old_profile["instances"][0]["rows"]
    new_rows = new_profile["instances"][0]["rows"]
    assert len(old_rows) == len(new_rows) == 2 and old_rows[1] == new_rows[1]
    cols = [col["name"] for col in old_profile["columns"]]
    changes = {cols[i]: [a, b] for i, (a, b) in enumerate(zip(old_rows[0], new_rows[0])) if a != b}
    assert changes == {"MINBS": [None, 7], "TPTIM": [None, 9.0], "TPTIMD": [None, "<EXP>"]}
    return {
        "schema": "simlox-e10-var08-subprofile-ignored-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "source_sha256": hashlib.sha256(build()).hexdigest(),
        "changed_tables": ["ProblemDescription", "TransportPolicyProfile"],
        "description_before": before["ProblemDescription"]["instances"][0]["rows"][0][0],
        "description_after": after["ProblemDescription"]["instances"][0]["rows"][0][0],
        "wrapper_field_changes": changes,
        "unchanged_child_basic_row": old_rows[1],
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
