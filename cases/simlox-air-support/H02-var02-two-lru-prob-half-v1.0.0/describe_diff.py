"""Freeze exact table names and source fingerprints for the preselected cohort."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, QTY_REFERENCE, QTY_REFERENCE_SHA, SEEDS


def sha(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path) -> dict:
    entries = json.loads(path.read_text(encoding="utf-8-sig"))["model"]["tables"]
    result = {entry["name"]: entry for entry in entries}
    assert len(result) == len(entries)
    return result


def changes(before: dict, after: dict) -> list[str]:
    assert before.keys() == after.keys()
    return sorted(name for name in before if before[name] != after[name])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assert sha(PARENT) == PARENT_SHA and sha(QTY_REFERENCE) == QTY_REFERENCE_SHA
    parent = tables(PARENT)
    control_path = HERE / "control-input.json"
    control = tables(control_path)
    parent_delta = changes(parent, control)
    assert parent_delta == ["DamageItem", "ItemStructure", "ProblemDescription", "StockAllocation"]
    arms = {}
    for seed in SEEDS:
        path = HERE / f"seed-{seed}-input.json"
        child = tables(path)
        delta = changes(control, child)
        assert delta == (["DamageItem", "ProblemDescription"] if seed == 1 else
                         ["Control", "DamageItem", "ProblemDescription"])
        before = control["DamageItem"]["instances"][0]["rows"][0]
        after = child["DamageItem"]["instances"][0]["rows"][0]
        assert before[:3] == after[:3] == ["BATTLE-HIT", "TEACH-AIR-01", "TEACH-LRU-01"]
        assert before[3] == 0 and after[3] == .5 and before[4:] == after[4:]
        arms[str(seed)] = {"sha256": sha(path), "changed_tables": delta,
                           "damage_probability_before": before[3],
                           "damage_probability_after": after[3],
                           "seed_before": "1", "seed_after": str(seed)}
    result = {"schema": "simlox-h02-var02-two-lru-prob-half-exact-diff/v1",
              "parent_sha256": sha(PARENT), "quantity_reference_sha256": sha(QTY_REFERENCE),
              "control_sha256": sha(control_path), "parent_to_control_changed_tables": parent_delta,
              "arms": arms, "preselected_seeds": list(SEEDS)}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    out = HERE / "exact-diff.json"
    if args.write:
        if out.exists():
            raise FileExistsError(out)
        out.write_bytes(raw)
    elif out.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": hashlib.sha256(raw).hexdigest(),
                      "parent_delta": parent_delta, "arms": len(arms)}))


if __name__ == "__main__":
    main()
