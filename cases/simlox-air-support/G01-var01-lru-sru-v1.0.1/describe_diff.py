"""Check the exact source delta against accepted E01 without modifying either input."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E01-local-spare-explicit-replacement-v1.0.0/native-input.json"
EXPECTED = {"ProblemDescription", "Item", "ItemStructure", "ItemRepair", "ItemReplacement", "StockAllocation"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    return {table["name"]: table for table in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main():
    before, after = tables(PARENT), tables(HERE / "native-input.json")
    if before.keys() != after.keys():
        raise ValueError("table set changed")
    changed = {name for name in before if before[name] != after[name]}
    if changed != EXPECTED:
        raise ValueError(f"unexpected changed tables: {sorted(changed)}")
    result = {
        "schema": "simlox-g01-var01-parent-diff/v1",
        "parent_sha256": sha(PARENT),
        "child_sha256": sha(HERE / "native-input.json"),
        "changed_tables": sorted(changed),
        "unchanged_tables": len(before) - len(changed),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
