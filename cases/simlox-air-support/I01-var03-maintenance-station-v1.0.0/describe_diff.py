"""Freeze parent-to-station-model and APID-only maintenance-point deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raws = [p.read_bytes() for p in (PARENT, HERE / "base-input.json", HERE / "depot-input.json")]
    assert sha(raws[0]) == PARENT_SHA
    parent, base, depot = (tables(raw) for raw in raws)
    p_to_b, b_to_d = delta(parent, base), delta(base, depot)
    assert set(p_to_b["added_tables"]) == {"TaskCategory", "TaskLevel", "MaintenanceAllocation"}
    assert not p_to_b["removed_tables"]
    assert set(p_to_b["changed_tables"]) == {
        "ProblemDescription", "Station", "StationStructure", "ItemRepair", "Tasks", "StockAllocation"}
    assert not b_to_d["added_tables"] and not b_to_d["removed_tables"]
    assert set(b_to_d["changed_tables"]) == {"Control", "ProblemDescription"}
    before = b_to_d["changed_tables"]["Control"]["before"]["instances"][0]["rows"][0]
    after = b_to_d["changed_tables"]["Control"]["after"]["instances"][0]["rows"][0]
    assert before[3] == "AIR_BASIC" and after[3] == "AIR_DEPOT"
    assert before[:3] == after[:3] and before[4:] == after[4:]
    result = {"schema": "simlox-i01-var03-maintenance-station-exact-diff/v1",
              "parent_sha256": sha(raws[0]), "base_sha256": sha(raws[1]),
              "depot_sha256": sha(raws[2]), "parent_to_base": p_to_b,
              "base_to_depot": b_to_d}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(json.dumps({"sha256": sha(raw), "added": sorted(p_to_b["added_tables"]),
                      "parent_changed": sorted(p_to_b["changed_tables"]),
                      "APID_changed": sorted(b_to_d["changed_tables"])}))


if __name__ == "__main__":
    main()
