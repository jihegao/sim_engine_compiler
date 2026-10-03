"""Assert the exact source delta and installed-count arithmetic."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def rowdata(t):
    return [row for inst in t["instances"] for row in inst["rows"]]


def main():
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("parent fingerprint differs")
    child = HERE / "native-input.json"
    before, after = tables(PARENT), tables(child)
    if before.keys() != after.keys():
        raise ValueError("table names changed")
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != ["ProblemDescription", "RedundancyLink"]:
        raise ValueError(f"unexpected delta {changed}")
    old, new = before["RedundancyLink"], after["RedundancyLink"]
    if old["columns"] != new["columns"]:
        raise ValueError("link columns changed")
    cols = [c["name"] for c in old["columns"]]
    old_rows, new_rows = rowdata(old), rowdata(new)
    if len(old_rows) != 2 or len(new_rows) != 2:
        raise ValueError("unexpected link row count")
    index = next(i for i, row in enumerate(old_rows) if row[cols.index("IID")] == "TEACH-LRU-01")
    expected = [list(row) for row in old_rows]
    expected[index][cols.index("QTYPL")] = 2
    if new_rows != expected:
        raise ValueError("more than one link quantity changed")
    record = {"schema": "simlox-g10-var08-v100-exact-diff/v1", "parent_sha256": sha(PARENT), "child_sha256": sha(child), "changed_tables": changed, "link_columns": cols, "link_before": old_rows, "link_after": new_rows, "installed_lru_qtypm": 2, "nrl": 2, "valid_total_lru": 2, "invalid_total_lru": 4}
    output = HERE / "exact-diff.json"
    raw = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if output.exists():
        if output.read_bytes() != raw:
            raise ValueError("frozen diff differs")
    else:
        output.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "child_sha256": record["child_sha256"]}))


if __name__ == "__main__":
    main()
