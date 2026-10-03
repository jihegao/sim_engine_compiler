"""Verify the exact four-cell delta from accepted G01.var01."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G01-var01-lru-sru-v1.0.1" / "native-input.json"
CHILD = HERE / "native-input.json"
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def diff() -> dict:
    old, new = keyed(json.loads(PARENT.read_text(encoding="utf-8"))), keyed(json.loads(CHILD.read_text(encoding="utf-8")))
    assert old.keys() == new.keys()
    changes = []
    for name in old:
        a, b = old[name], new[name]
        assert a["columns"] == b["columns"]
        assert len(a["instances"]) == len(b["instances"]) == 1
        names = [c["name"] for c in a["columns"]]
        left, right = a["instances"][0]["rows"], b["instances"][0]["rows"]
        assert len(left) == len(right)
        for i, (ar, br) in enumerate(zip(left, right)):
            assert len(ar) == len(br) == len(names)
            for field, av, bv in zip(names, ar, br):
                if av != bv:
                    changes.append({"table": name, "row": i, "field": field, "before": av, "after": bv})
    assert [(x["table"], x["row"], x["field"]) for x in changes] == [
        ("ProblemDescription", 0, "PDESC"), ("System", 0, "FRT"),
        ("Item", 0, "FRT"), ("Item", 1, "FRT")]
    return {"schema": "simlox-f01-var01-g01-diff/v1", "parent_sha256": sha(PARENT), "child_sha256": sha(CHILD),
            "changes": changes, "unchanged_tables": len(old) - 3}


def main() -> None:
    raw = (json.dumps(diff(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if OUT.exists():
        assert OUT.read_bytes() == raw
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(), "changes": 4}))


if __name__ == "__main__":
    main()
