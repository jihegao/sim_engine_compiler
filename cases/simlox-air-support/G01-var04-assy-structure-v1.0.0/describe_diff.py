"""Verify the bounded ASSY delta against accepted G01.var01."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var01-lru-sru-v1.0.1/native-input.json"
EXPECTED = {"ProblemDescription", "Item", "ItemStructure", "ItemReplacement"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main():
    before, after = tables(PARENT), tables(HERE / "native-input.json")
    if before.keys() != after.keys():
        raise ValueError("table set changed")
    changed = {name for name in before if before[name] != after[name]}
    if changed != EXPECTED:
        raise ValueError(f"unexpected changed tables: {sorted(changed)}")
    print(json.dumps({"schema": "simlox-g01-var04-parent-diff/v1", "parent_sha256": sha(PARENT), "child_sha256": sha(HERE / "native-input.json"), "changed_tables": sorted(changed), "unchanged_tables": len(before) - len(changed)}, indent=2))


if __name__ == "__main__":
    main()
