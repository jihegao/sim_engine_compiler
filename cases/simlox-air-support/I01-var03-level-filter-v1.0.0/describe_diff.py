"""Freeze the four-arm task-level/APID matrix and its exact source deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA

ARMS = ("basic-base", "depot-base", "basic-alternate", "depot-alternate")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    out = {item["name"]: item for item in items}
    assert len(out) == len(items)
    return out


def delta(before: dict, after: dict) -> dict:
    return {"added_tables": {n: after[n] for n in sorted(after.keys() - before.keys())},
            "removed_tables": {n: before[n] for n in sorted(before.keys() - after.keys())},
            "changed_tables": {n: {"before": before[n], "after": after[n]}
                               for n in before if n in after and before[n] != after[n]},
            "unchanged_table_count": sum(before[n] == after[n] for n in before.keys() & after.keys())}


def single_rows(table: dict) -> list[list]:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def check_apid_diff(diff: dict, before: str, after: str) -> None:
    assert not diff["added_tables"] and not diff["removed_tables"]
    assert set(diff["changed_tables"]) == {"Control", "ProblemDescription"}
    control = diff["changed_tables"]["Control"]
    a, b = single_rows(control["before"])[0], single_rows(control["after"])[0]
    assert a[3] == before and b[3] == after and a[:3] == b[:3] and a[4:] == b[4:]


def check_level_diff(diff: dict) -> None:
    assert not diff["added_tables"] and not diff["removed_tables"]
    assert set(diff["changed_tables"]) == {"Tasks", "ProblemDescription"}
    tasks = diff["changed_tables"]["Tasks"]
    before, after = single_rows(tasks["before"]), single_rows(tasks["after"])
    assert len(before) == len(after)
    changed = {}
    for a, b in zip(before, after):
        assert a[0] == b[0] and a[:3] == b[:3] and a[4:] == b[4:]
        if a[3] != b[3]:
            changed[a[0]] = (a[3], b[3])
    assert changed == {"I01-LRU-DIRP": ("BASE", "ALT"),
                       "I01-LEVEL-B": ("ALT", "BASE")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raws = {"parent": PARENT.read_bytes(), **{
        arm: (HERE / f"{arm}-input.json").read_bytes() for arm in ARMS}}
    assert sha(raws["parent"]) == PARENT_SHA
    t = {name: tables(raw) for name, raw in raws.items()}
    d = {
        "parent_to_basic_base": delta(t["parent"], t["basic-base"]),
        "basic_base_to_depot_base": delta(t["basic-base"], t["depot-base"]),
        "basic_base_to_basic_alternate": delta(t["basic-base"], t["basic-alternate"]),
        "depot_base_to_depot_alternate": delta(t["depot-base"], t["depot-alternate"]),
        "basic_alternate_to_depot_alternate": delta(t["basic-alternate"], t["depot-alternate"]),
    }
    assert not d["parent_to_basic_base"]["added_tables"] and not d["parent_to_basic_base"]["removed_tables"]
    assert set(d["parent_to_basic_base"]["changed_tables"]) == {
        "ProblemDescription", "Tasks", "TaskLevel", "MaintenanceAllocation"}
    check_apid_diff(d["basic_base_to_depot_base"], "AIR_BASIC", "AIR_DEPOT")
    check_apid_diff(d["basic_alternate_to_depot_alternate"], "AIR_BASIC", "AIR_DEPOT")
    check_level_diff(d["basic_base_to_basic_alternate"])
    check_level_diff(d["depot_base_to_depot_alternate"])
    result = {"schema": "simlox-i01-var03-level-apid-matrix-exact-diff/v1",
              "source_sha256": {name: sha(raw) for name, raw in raws.items()}, "deltas": d}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(json.dumps({"sha256": sha(raw), "source_sha256": result["source_sha256"]}))


if __name__ == "__main__":
    main()
