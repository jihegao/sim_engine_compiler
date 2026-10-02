"""Freeze all eight exact source deltas against accepted REPF1 input."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, SEEDS


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    result = {item["name"]: item for item in items}
    if len(result) != len(items):
        raise ValueError("duplicate source table")
    return result


def value(table: dict, column: str) -> object:
    columns = [c["name"] for c in table["columns"]]
    rows = [r for i in table["instances"] for r in i["rows"]]
    assert len(rows) == 1
    return rows[0][columns.index(column)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA
    before = tables(parent_raw)
    result = {"schema": "simlox-h02-var03-repf-half-seeds-exact-diff/v1",
              "parent_sha256": PARENT_SHA, "preselected_seeds": list(SEEDS), "arms": {}}
    for seed in SEEDS:
        raw = (HERE / f"seed-{seed}-input.json").read_bytes()
        after = tables(raw)
        added = sorted(after.keys() - before.keys())
        removed = sorted(before.keys() - after.keys())
        changed = sorted(name for name in before if name in after and before[name] != after[name])
        expected = ["DamageItem", "ProblemDescription"] if seed == 1 else [
            "Control", "DamageItem", "ProblemDescription"]
        assert not added and not removed and changed == expected
        assert value(after["DamageItem"], "REPF") == .5
        assert value(after["Control"], "RSEED") == str(seed)
        assert value(after["ProblemDescription"], "PDESC") == (
            f"H02.var03 primary LRU damage REPF half seed {seed}")
        result["arms"][str(seed)] = {
            "input_sha256": sha(raw), "added_tables": added, "removed_tables": removed,
            "changed_tables": changed, "unchanged_table_count": len(before) - len(changed),
            "values": {"REPF_before": value(before["DamageItem"], "REPF"),
                       "REPF_after": .5, "RSEED_before": value(before["Control"], "RSEED"),
                       "RSEED_after": str(seed)}}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(raw)
    elif output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": sha(raw), "seeds": list(SEEDS)}))


if __name__ == "__main__":
    main()
