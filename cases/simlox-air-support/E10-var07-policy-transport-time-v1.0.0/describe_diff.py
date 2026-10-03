"""Assert exact parent and paired-arm policy transport-time changes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import HERE, PARENT, PARENT_SHA, ARMS, build, sha

OUTPUT = HERE / "exact-diff.json"


def maps(doc: dict) -> dict:
    tables = doc["model"]["tables"]
    result = {t["name"]: t for t in tables}
    assert len(result) == len(tables)
    return result


def row(t: dict) -> list:
    assert len(t["instances"]) == 1 and len(t["instances"][0]["rows"]) == 1
    return t["instances"][0]["rows"][0]


def describe() -> dict:
    assert sha(PARENT) == PARENT_SHA
    parent = maps(json.loads(PARENT.read_text(encoding="utf-8-sig")))
    arms = {arm: maps(json.loads(build(arm))) for arm in ARMS}
    assert set(parent) == set(arms["det3"]) == set(arms["exp3"])
    changed_parent = {"ProblemDescription", "TransportPolicyProfile"}
    assert all({n for n in parent if parent[n] != arms[a][n]} == changed_parent for a in ARMS)
    assert {n for n in parent if arms["det3"][n] != arms["exp3"][n]} == changed_parent
    profile = parent["TransportPolicyProfile"]
    names = [c["name"] for c in profile["columns"]]
    i_time, i_dist = names.index("TPTIM"), names.index("TPTIMD")
    old = row(profile)
    assert old[i_time] == 2.0 and old[i_dist] is None
    for arm in ARMS:
        t = arms[arm]["TransportPolicyProfile"]
        assert t["columns"] == profile["columns"]
        current = row(t)
        assert current[i_time] == 3.0 and current[i_dist] == ("<EXP>" if arm == "exp3" else None)
        assert all(a == b for i, (a, b) in enumerate(zip(old, current)) if i not in {i_time, i_dist})
    link = row(parent["StationStructure"])
    link_names = [c["name"] for c in parent["StationStructure"]["columns"]]
    assert link[link_names.index("TFRMS")] == 2.0 and link[link_names.index("PFRMS")] == "DOWN-POLICY"
    return {
        "schema": "simlox-e10-var07-policy-transport-time-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "inputs_sha256": {arm: hashlib.sha256(build(arm)).hexdigest() for arm in ARMS},
        "changed_tables_parent_to_each_arm": sorted(changed_parent),
        "changed_tables_between_arms": sorted(changed_parent),
        "parent_downward_link_tfrms": 2.0,
        "parent_policy_row": old,
        "det3_policy_row": row(arms["det3"]["TransportPolicyProfile"]),
        "exp3_policy_row": row(arms["exp3"]["TransportPolicyProfile"]),
        "unchanged_tables": len(parent) - len(changed_parent),
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
