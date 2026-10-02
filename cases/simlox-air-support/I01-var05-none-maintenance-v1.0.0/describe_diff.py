"""Freeze parent-to-maintenance-model and APID-only <NONE> point delta."""
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
    raws = [p.read_bytes() for p in (PARENT, HERE / "matching-input.json", HERE / "none-input.json")]
    assert sha(raws[0]) == PARENT_SHA
    parent, matching, none = (tables(raw) for raw in raws)
    p_to_m, m_to_o = delta(parent, matching), delta(matching, none)
    assert set(p_to_m["added_tables"]) == {"TaskCategory", "TaskLevel", "MaintenanceAllocation"}
    assert not p_to_m["removed_tables"]
    assert set(p_to_m["changed_tables"]) == {
        "ItemRepair", "Tasks", "StockAllocation", "ProblemDescription"}
    assert not m_to_o["added_tables"] and not m_to_o["removed_tables"]
    assert set(m_to_o["changed_tables"]) == {"Control", "ProblemDescription"}
    assert m_to_o["changed_tables"]["Control"]["before"]["instances"][0]["rows"][0][3] == "AIR_BASIC"
    assert m_to_o["changed_tables"]["Control"]["after"]["instances"][0]["rows"][0][3] == "AIR_NONE"
    result = {"schema": "simlox-i01-var05-none-maintenance-exact-diff/v1",
              "parent_sha256": sha(raws[0]), "matching_sha256": sha(raws[1]),
              "none_sha256": sha(raws[2]), "parent_to_matching": p_to_m,
              "matching_to_none": m_to_o}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(json.dumps({"sha256": sha(raw), "added": sorted(p_to_m["added_tables"]),
                      "parent_changed": sorted(p_to_m["changed_tables"]),
                      "APID_changed": sorted(m_to_o["changed_tables"])}))


if __name__ == "__main__":
    main()
