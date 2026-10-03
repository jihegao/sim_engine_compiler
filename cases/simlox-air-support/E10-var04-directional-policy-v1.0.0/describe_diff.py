"""Check the exact ONDEM-parent to directional-policy model delta."""
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
    assert {name for name in before if before[name] != after[name]} == {"ProblemDescription", "StationStructure", "TransportPolicyProfile"}
    b, a = before["StationStructure"], after["StationStructure"]
    assert b["columns"] == a["columns"] and b["instances"][0]["instance_name"] == a["instances"][0]["instance_name"]
    names = [c["name"] for c in b["columns"]]
    old, new = b["instances"][0]["rows"], a["instances"][0]["rows"]
    assert len(old) == len(new) == 1
    changes = [{"field": names[i], "before": x, "after": y} for i, (x, y) in enumerate(zip(old[0], new[0])) if x != y]
    assert changes == [{"field": "PTOMS", "before": None, "after": "UP-POLICY"}]
    old_profile, new_profile = before["TransportPolicyProfile"], after["TransportPolicyProfile"]
    assert old_profile["columns"] == new_profile["columns"]
    old_rows, new_rows = old_profile["instances"][0]["rows"], new_profile["instances"][0]["rows"]
    assert len(old_rows) == 1 and new_rows == old_rows + [["UP-POLICY", "FIXED", 11.0, 1, 0.0, None, 1, 2.0, None, None]]
    old_desc = before["ProblemDescription"]["instances"][0]["rows"]
    new_desc = after["ProblemDescription"]["instances"][0]["rows"]
    assert len(old_desc) == len(new_desc) == 1
    return {
        "schema": "simlox-e10-var04-directional-policy-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "source_sha256": hashlib.sha256(build()).hexdigest(),
        "changed_tables": ["ProblemDescription", "StationStructure", "TransportPolicyProfile"],
        "station_structure_delta": changes,
        "unchanged_downward_profile_row": old_rows[0],
        "added_upward_profile_row": new_rows[1],
        "description_before": old_desc[0][0],
        "description_after": new_desc[0][0],
        "unchanged_parent_tables": len(before) - 3,
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
