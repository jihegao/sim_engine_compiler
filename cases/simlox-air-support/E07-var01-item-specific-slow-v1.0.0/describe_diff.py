"""Verify the complete E07 FAST-to-SLOW source delta."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build import HERE, OUTPUT, PARENT, PARENT_SHA, build, table

DIFF = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def diff() -> dict:
    parent = json.loads(PARENT.read_bytes())
    child = json.loads(OUTPUT.read_bytes())
    if child != build() or sha(PARENT) != PARENT_SHA:
        raise AssertionError("frozen input or parent differs from builder")
    parent_description = table(parent, "ProblemDescription")["instances"][0]["rows"][0][0]
    child_description = table(child, "ProblemDescription")["instances"][0]["rows"][0][0]
    parent_item = table(parent, "ItemStationStructure")
    child_item = table(child, "ItemStationStructure")
    columns = [column["name"] for column in parent_item["columns"]]
    index = columns.index("OPOL")
    parent_policy = parent_item["instances"][0]["rows"][0][index]
    child_policy = child_item["instances"][0]["rows"][0][index]
    if parent_policy != "FAST" or child_policy != "SLOW":
        raise AssertionError("expected sole behavior change FAST to SLOW")
    changed = {p["name"] for p, c in zip(parent["model"]["tables"], child["model"]["tables"]) if p != c}
    if len(parent["model"]["tables"]) != len(child["model"]["tables"]) or changed != {"ProblemDescription", "ItemStationStructure"}:
        raise AssertionError("unexpected table delta")
    return {"schema": "simlox-e07-item-slow-exact-delta/v1", "parent_sha256": sha(PARENT),
            "input_sha256": sha(OUTPUT), "changed_tables": sorted(changed),
            "changed_cells": [
                {"table": "ProblemDescription", "key": "sole row", "field": "PDESC", "from": parent_description, "to": child_description},
                {"table": "ItemStationStructure", "key": "TEACH-LRU-01/BASE-01/DEPOT-01", "field": "OPOL", "from": parent_policy, "to": child_policy}
            ]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(diff(), indent=2) + "\n").encode("utf-8")
    if args.write:
        if DIFF.exists():
            raise FileExistsError(DIFF)
        DIFF.write_bytes(raw)
    elif DIFF.read_bytes() != raw:
        raise AssertionError("frozen exact diff differs")
    print(json.dumps({"exact_parent_delta": True, "input_sha256": sha(OUTPUT)}))


if __name__ == "__main__":
    main()
