"""Verify the complete E04-to-E07 source delta, including new table schema."""
import argparse
import json
from pathlib import Path

from build import HERE, PARENT, build

OUTPUT = HERE / "exact-diff.json"


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def diff():
    parent = {table["name"]: table for table in json.loads(PARENT.read_text(encoding="utf-8"))["model"]["tables"]}
    child = {table["name"]: table for table in build()["model"]["tables"]}
    if set(parent) - set(child) or set(child) - set(parent) != {"ItemStationStructure"}:
        raise AssertionError("unexpected table removal/addition")
    changed = {name: {"parent_columns": parent[name]["columns"] if name in parent else None,
                      "child_columns": child[name]["columns"],
                      "parent_rows": rows(parent[name]) if name in parent else None,
                      "child_rows": rows(child[name])}
               for name in child if name not in parent or parent[name] != child[name]}
    if set(changed) != {"ProblemDescription", "ItemStationStructure"}:
        raise AssertionError("unexpected source delta")
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(diff(), indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise AssertionError("frozen exact diff differs")
    print("E07 exact parent delta verified")


if __name__ == "__main__":
    main()
