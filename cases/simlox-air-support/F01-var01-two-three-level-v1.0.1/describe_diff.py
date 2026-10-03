"""Verify both exact parent deltas and the six-table topology contrast."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES = {
    "e05": ROOT / "E05-local-repair-reissue-v1.0.0/native-input.json",
    "g01": ROOT / "G01-var01-lru-sru-v1.0.1/native-input.json",
    "two": HERE / "two-level-input.json",
    "three": HERE / "three-level-input.json",
}
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    result = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def compare(left: Path, right: Path) -> dict:
    a, b = tables(left), tables(right)
    assert a.keys() == b.keys()
    changed = []
    for name in a:
        x, y = a[name], b[name]
        assert x["columns"] == y["columns"]
        if x["instances"] != y["instances"]:
            assert len(x["instances"]) == len(y["instances"]) == 1
            changed.append({"table": name, "before_rows": x["instances"][0]["rows"], "after_rows": y["instances"][0]["rows"]})
    return {"left_sha256": sha(left), "right_sha256": sha(right), "changed_tables": changed,
            "unchanged_tables": len(a) - len(changed)}


def build() -> dict:
    p = compare(SOURCES["e05"], SOURCES["two"])
    q = compare(SOURCES["g01"], SOURCES["three"])
    pair = compare(SOURCES["two"], SOURCES["three"])
    assert [x["table"] for x in p["changed_tables"]] == ["ProblemDescription", "System", "Item"]
    assert [x["table"] for x in q["changed_tables"]] == ["ProblemDescription", "System", "Item"]
    assert [x["table"] for x in pair["changed_tables"]] == ["ProblemDescription", "Item", "ItemStructure", "ItemRepair", "StockAllocation", "ItemReplacement"]
    assert p["unchanged_tables"] == q["unchanged_tables"] == 28 and pair["unchanged_tables"] == 25
    return {"schema": "simlox-f01-var01-two-three-exact-diffs/v1", "two_from_e05": p,
            "three_from_g01": q, "three_from_two": pair}


def main() -> None:
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        assert OUT.read_bytes() == raw
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "paired_changed_tables": 6}))


if __name__ == "__main__":
    main()
