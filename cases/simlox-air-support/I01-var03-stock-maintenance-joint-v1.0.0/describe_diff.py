"""Freeze the four-POINT stock/maintenance diagnostic source deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA

ARMS = ("one-base", "one-depot", "two-base", "two-depot")


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raws = {"parent": PARENT.read_bytes(), **{
        arm: (HERE / f"{arm}-input.json").read_bytes() for arm in ARMS}}
    assert sha(raws["parent"]) == PARENT_SHA
    t = {name: tables(raw) for name, raw in raws.items()}
    d = {
        "parent_to_one_base": delta(t["parent"], t["one-base"]),
        "one_base_to_one_depot": delta(t["one-base"], t["one-depot"]),
        "one_base_to_two_base": delta(t["one-base"], t["two-base"]),
        "one_depot_to_two_depot": delta(t["one-depot"], t["two-depot"]),
        "two_base_to_two_depot": delta(t["two-base"], t["two-depot"]),
    }
    assert not d["parent_to_one_base"]["added_tables"] and not d["parent_to_one_base"]["removed_tables"]
    assert set(d["parent_to_one_base"]["changed_tables"]) == {
        "ProblemDescription", "StockAllocation", "MaintenanceAllocation"}
    for key, before, after in (
        ("one_base_to_one_depot", "AIR_BASIC", "AIR_DEPOT"),
        ("one_base_to_two_base", "AIR_BASIC", "AIR_TWO_BASE"),
        ("one_depot_to_two_depot", "AIR_DEPOT", "AIR_TWO_DEPOT"),
        ("two_base_to_two_depot", "AIR_TWO_BASE", "AIR_TWO_DEPOT"),
    ):
        check_apid_diff(d[key], before, after)
    result = {"schema": "simlox-i01-var03-joint-stock-maintenance-exact-diff/v1",
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
