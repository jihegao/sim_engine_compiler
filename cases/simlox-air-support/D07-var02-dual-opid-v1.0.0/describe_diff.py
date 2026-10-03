"""Verify the complete D02.var01 -> D07.var02 authored table delta."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

from build import PARENT, OUTPUT, table


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before = json.loads(PARENT.read_bytes())
    after = json.loads(OUTPUT.read_bytes())
    old = {t["name"]: t for t in before["model"]["tables"]}
    new = {t["name"]: t for t in after["model"]["tables"]}
    changed = {name for name in old.keys() & new.keys() if old[name] != new[name]}
    added = set(new) - set(old)
    removed = set(old) - set(new)
    assert changed == {"ProblemDescription", "OperationParameter"}, changed
    assert added == {"MissionTypeUtilization", "ItemFailureRate", "SystemFailureRate"}, added
    assert not removed, removed
    assert old["ProblemDescription"]["columns"] == new["ProblemDescription"]["columns"]
    assert table(list(new.values()), "OperationParameter")["instances"][0]["rows"] == [
        ["KM", "Custom distance in kilometres", None]
    ]
    assert new["MissionTypeUtilization"]["instances"][0]["rows"] == [
        ["BASIC-MISSION", "TEACH-AIR-01", "KM", 60.0, "1/HOUR", None]
    ]
    assert new["ItemFailureRate"]["instances"][0]["rows"] == [
        ["TEACH-LRU-01", "KM", 5000.0, None]
    ]
    assert new["SystemFailureRate"]["instances"][0]["rows"] == [
        ["TEACH-AIR-01", "KM", 5000.0, None]
    ]
    assert before.keys() == after.keys()
    diff = {
        "schema": "simlox-d07-var02-exact-parent-diff/v1",
        "parent_case": "D02.var01",
        "child_case": "D07.var02",
        "changed_tables": {name: {"before": old[name], "after": new[name]} for name in sorted(changed)},
        "added_tables": {name: new[name] for name in sorted(added)},
        "removed_tables": {},
    }
    output = Path(__file__).with_name("parent-diff.json")
    raw = json.dumps(diff, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_text(raw, encoding="utf-8")
    elif output.read_text(encoding="utf-8") != raw:
        raise ValueError("frozen exact parent diff differs")
    print(json.dumps({"changed_tables": sorted(changed), "added_tables": sorted(added), "removed_tables": []}))


if __name__ == "__main__":
    main()
