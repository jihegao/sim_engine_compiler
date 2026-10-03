"""Reproduce and check the exact E04-to-E10 and paired business deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import ARMS, HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def cell_changes(before: dict, after: dict, name: str) -> list[dict]:
    b, a = before[name], after[name]
    assert [c["name"] for c in b["columns"]] == [c["name"] for c in a["columns"]]
    cols = [c["name"] for c in b["columns"]]
    br = [r for i in b["instances"] for r in i["rows"]]
    ar = [r for i in a["instances"] for r in i["rows"]]
    assert len(br) == len(ar)
    return [{"table": name, "row": i, "field": cols[j], "before": x, "after": y}
            for i, (row_b, row_a) in enumerate(zip(br, ar))
            for j, (x, y) in enumerate(zip(row_b, row_a)) if x != y]


def describe() -> dict:
    assert sha(PARENT) == PARENT_SHA
    before = tables(json.loads(PARENT.read_text(encoding="utf-8-sig")))
    children = {arm: tables(json.loads(build(arm))) for arm in ARMS}
    expected = {
        "fixed": {"STPRID": "FIXED", "STIM": 11.0, "DURN": None},
        "ondem": {"STPRID": "ONDEM", "STIM": 0.0, "DURN": 36.0},
    }
    for arm, after in children.items():
        assert set(after) - set(before) == {"TransportPolicyProfile"}
        assert set(before) - set(after) == set()
        assert {name for name in before if before[name] != after[name]} == {"ProblemDescription", "StationStructure"}
        changes = cell_changes(before, after, "StationStructure")
        assert changes == [{"table": "StationStructure", "row": 0, "field": "PFRMS", "before": None, "after": "DOWN-POLICY"}]
        profile = after["TransportPolicyProfile"]
        names = [c["name"] for c in profile["columns"]]
        assert [c["name"] for c in profile["columns"] if c.get("key")] == ["TPRID", "STPRID", "STIM"]
        row = profile["instances"][0]["rows"][0]
        assert len(row) == len(names) == 10
        assert {k: row[names.index(k)] for k in expected[arm]} == expected[arm]
        assert row[names.index("TPRID")] == "DOWN-POLICY" and row[names.index("TPTIM")] == 2.0 and row[names.index("MINBS")] == 1
    pair = {name for name in children["fixed"] if children["fixed"][name] != children["ondem"][name]}
    assert pair == {"ProblemDescription", "TransportPolicyProfile"}
    return {
        "schema": "simlox-e10-var01-transport-policy-exact-diff/v1",
        "parent_sha256": PARENT_SHA,
        "source_sha256": {arm: hashlib.sha256(build(arm)).hexdigest() for arm in ARMS},
        "changed_parent_tables": ["ProblemDescription", "StationStructure"],
        "added_table": "TransportPolicyProfile",
        "station_structure_delta": changes,
        "pairwise_changed_tables": sorted(pair),
        "pairwise_policy_fields": {"fixed": expected["fixed"], "ondem": expected["ondem"]},
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
