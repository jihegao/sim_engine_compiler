"""Check and freeze the exact parent table changes for both G04 RBD arms."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build import ARMS, PARENT, PARENT_SHA, build

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    assert sha(PARENT) == PARENT_SHA
    original = {t["name"]: t for t in parent["model"]["tables"]}
    result = {"schema": "g04-series-active-parallel-exact-diff/v1", "parent_sha256": PARENT_SHA, "arms": {}}
    for arm in ARMS:
        path = HERE / f"{arm}-input.json"
        child = json.loads(path.read_text(encoding="utf-8"))
        assert child == build(arm)
        actual = {t["name"]: t for t in child["model"]["tables"]}
        changed = sorted(name for name in original if original[name] != actual[name])
        added = sorted(set(actual) - set(original))
        expected_added = sorted(["OperationalModes", "MissionOperationalModes", "MaterielOperationalModes",
                                 "RBDSeries" if arm == "series" else "RBDParallel",
                                 "RBDSeriesStructure" if arm == "series" else "RBDParallelStructure"])
        assert changed == ["Control", "ProblemDescription"] and added == expected_added
        assert len(actual) == len(original) + 5
        result["arms"][arm] = {"input_sha256": sha(path), "changed_existing_tables": changed,
                                "added_tables": added, "unchanged_existing_tables": len(original) - len(changed)}
    raw = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen exact-diff differs")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
