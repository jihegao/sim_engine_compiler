"""Verify the exact accepted D07.var02 to D07.var03 table delta."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build import PARENT, OUTPUT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    before = json.loads(PARENT.read_bytes())
    after = json.loads(OUTPUT.read_bytes())
    old = {t["name"]: t for t in before["model"]["tables"]}
    new = {t["name"]: t for t in after["model"]["tables"]}
    changed = {n for n in old.keys() & new.keys() if old[n] != new[n]}
    assert changed == {"ProblemDescription", "ItemFailureRate", "SystemFailureRate"}, changed
    assert old.keys() == new.keys()
    for name, id_ in (("ItemFailureRate", "TEACH-LRU-01"), ("SystemFailureRate", "TEACH-AIR-01")):
        assert old[name]["columns"] == new[name]["columns"]
        assert new[name]["instances"][0]["rows"] == old[name]["instances"][0]["rows"] + [[id_, "OPHOURS", 100000.0, None]]
    diff = {
        "schema": "simlox-d07-var03-exact-parent-diff/v1",
        "parent_case": "D07.var02",
        "child_case": "D07.var03",
        "changed_tables": {name: {"before": old[name], "after": new[name]} for name in sorted(changed)},
        "added_tables": {},
        "removed_tables": {},
    }
    output = Path(__file__).with_name("parent-diff.json")
    raw = json.dumps(diff, ensure_ascii=False, indent=2) + "\n"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_text(raw, encoding="utf-8")
    elif output.read_text(encoding="utf-8") != raw:
        raise ValueError("frozen parent diff differs")
    print(json.dumps({"changed_tables": sorted(changed), "added_tables": [], "removed_tables": []}))


if __name__ == "__main__":
    main()
