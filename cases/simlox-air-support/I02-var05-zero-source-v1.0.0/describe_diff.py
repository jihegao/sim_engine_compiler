"""Freeze accepted-parent to h2 control and control to zero-source child deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"]) == 32
    return result


def delta(left_path: Path, right_path: Path) -> dict:
    left, right = tables(left_path), tables(right_path)
    assert set(left) == set(right)
    changed = {name: {"before": left[name], "after": right[name]}
               for name in sorted(left) if left[name] != right[name]}
    return {"before_sha256": sha(left_path), "after_sha256": sha(right_path),
            "changed_tables": changed, "unchanged_table_count": len(left) - len(changed)}


def main() -> None:
    assert sha(PARENT) == PARENT_SHA
    parent_to_control = delta(PARENT, HERE / "control-input.json")
    control_to_child = delta(HERE / "control-input.json", HERE / "native-input.json")
    assert set(parent_to_control["changed_tables"]) == {"ProblemDescription", "ItemTransfer"}
    assert set(control_to_child["changed_tables"]) == {"ProblemDescription", "StockAllocation"}
    assert parent_to_control["changed_tables"]["ItemTransfer"]["before"]["instances"][0]["rows"][1] == [
        "DEPOT-01", "BASE-01", "TEACH-LRU-01", 6.0, 1, 0.0, None]
    assert parent_to_control["changed_tables"]["ItemTransfer"]["after"]["instances"][0]["rows"][1] == [
        "DEPOT-01", "BASE-01", "TEACH-LRU-01", 2.0, 1, 0.0, None]
    assert control_to_child["changed_tables"]["StockAllocation"]["before"]["instances"][0]["rows"][1] == [
        "AIR_BASIC", "TEACH-LRU-01", "DEPOT-01", 1, None, None, None, None, None]
    assert control_to_child["changed_tables"]["StockAllocation"]["after"]["instances"][0]["rows"][1] == [
        "AIR_BASIC", "TEACH-LRU-01", "DEPOT-01", 0, None, None, None, None, None]
    result = {"schema": "simlox-i02-var05-zero-source-exact-diff/v1",
              "accepted_parent_to_control": parent_to_control,
              "matched_control_to_child": control_to_child}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"sha256": sha(output), "changed_tables": [2, 2]}))


if __name__ == "__main__":
    main()
