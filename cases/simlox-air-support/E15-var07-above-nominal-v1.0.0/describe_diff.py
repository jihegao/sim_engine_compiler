"""Verify the E15.var07 above-nominal child changes only PDESC and ISTOH."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E15-var07-explicit-istoh-v1.0.1/native-input-default.json"
CHILD = HERE / "native-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_map(path: Path) -> dict[str, dict]:
    doc = json.loads(path.read_bytes())
    tables = doc["model"]["tables"]
    result = {t["name"]: t for t in tables}
    if len(result) != len(tables):
        raise ValueError("duplicate tables")
    return result


def main() -> None:
    before, after = table_map(PARENT), table_map(CHILD)
    if set(before) != set(after):
        raise ValueError("table set differs")
    changes = []
    for name in sorted(before):
        old, new = before[name], after[name]
        if old == new:
            continue
        if old["columns"] != new["columns"] or len(old["instances"]) != 1 or len(new["instances"]) != 1:
            raise ValueError(f"structure changed in {name}")
        old_rows, new_rows = old["instances"][0]["rows"], new["instances"][0]["rows"]
        if len(old_rows) != len(new_rows):
            raise ValueError(f"rows changed in {name}")
        fields = [x["name"] for x in old["columns"]]
        for row_index, (a, b) in enumerate(zip(old_rows, new_rows)):
            for field, left, right in zip(fields, a, b):
                if left != right:
                    changes.append({"table": name, "row": row_index, "field": field, "before": left, "after": right})
    if [(x["table"], x["row"], x["field"], x["before"], x["after"]) for x in changes] != [
        ("ProblemDescription", 0, "PDESC", "E15.var07 tracked stock reorder initial depot on-hand default", "E15.var07 explicit depot ISTOH6 above nominal STSIZ4"),
        ("StockAllocation", 1, "ISTOH", None, 6),
    ]:
        raise ValueError("unexpected semantic delta")
    result = {"schema": "simlox-e15-var07-above-nominal-exact-diff/v1", "parent_sha256": sha(PARENT), "child_sha256": sha(CHILD), "changes": changes, "unchanged_tables": len(before) - 2}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
