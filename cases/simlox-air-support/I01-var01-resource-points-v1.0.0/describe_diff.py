"""Freeze C01-parent-to-resource-POINT and APID-only source deltas."""
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
    assert before.keys() == after.keys()
    changed = {name: {"before": before[name], "after": after[name]}
               for name in before if before[name] != after[name]}
    return {"changed_tables": changed, "unchanged_table_count": len(before) - len(changed)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raws = [p.read_bytes() for p in
            (PARENT, HERE / "selected-input.json", HERE / "zero-input.json")]
    assert sha(raws[0]) == PARENT_SHA
    parent, selected, zero = (tables(raw) for raw in raws)
    p_to_s, s_to_z = delta(parent, selected), delta(selected, zero)
    assert set(p_to_s["changed_tables"]) == {"ResourceAllocation", "ProblemDescription"}
    assert set(s_to_z["changed_tables"]) == {"Control", "ProblemDescription"}
    resource_before = p_to_s["changed_tables"]["ResourceAllocation"]["before"]["instances"][0]["rows"]
    resource_after = p_to_s["changed_tables"]["ResourceAllocation"]["after"]["instances"][0]["rows"]
    assert resource_after == resource_before + [
        ["AIR_ZERO", "P-CREW", "BASE-01", 0, None],
        ["AIR_ZERO", "P-OTHER", "BASE-01", 0, None],
    ]
    assert s_to_z["changed_tables"]["Control"]["before"]["instances"][0]["rows"][0][3] == "AIR_BASIC"
    assert s_to_z["changed_tables"]["Control"]["after"]["instances"][0]["rows"][0][3] == "AIR_ZERO"
    result = {
        "schema": "simlox-i01-var01-resource-points-exact-diff/v1",
        "parent_sha256": sha(raws[0]), "selected_sha256": sha(raws[1]),
        "zero_sha256": sha(raws[2]), "parent_to_selected": p_to_s,
        "selected_to_zero": s_to_z,
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    out = HERE / "exact-diff.json"
    if args.write:
        if out.exists():
            raise FileExistsError(out)
        out.write_bytes(data)
    elif out.read_bytes() != data:
        raise ValueError("frozen diff differs")
    print(json.dumps({"sha256": sha(data), "parent_changed": sorted(p_to_s["changed_tables"]),
                      "pair_changed": sorted(s_to_z["changed_tables"])}))


if __name__ == "__main__":
    main()
