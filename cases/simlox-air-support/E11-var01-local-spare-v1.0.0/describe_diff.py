"""Check the exact accepted E11 base to one-local-spare delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(before) == set(after)
    changed = {n for n in before if before[n] != after[n]}
    assert changed == {"ProblemDescription", "StockAllocation"}
    changes = []
    for name in sorted(changed):
        old, new = before[name], after[name]
        assert old["columns"] == new["columns"]
        assert len(old["instances"]) == len(new["instances"]) == 1
        a, b = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert len(a) == len(b)
        columns = [c["name"] for c in old["columns"]]
        for ri, (ar, br) in enumerate(zip(a, b)):
            for ci, (x, y) in enumerate(zip(ar, br)):
                if x != y:
                    changes.append({"table": name, "row": ri, "column": columns[ci], "before": x, "after": y})
    assert [(x["table"], x["row"], x["column"]) for x in changes] == [
        ("ProblemDescription", 0, "PDESC"), ("StockAllocation", 0, "STSIZ")
    ]
    return {"schema": "simlox-e11-var01-local-spare-exact-diff/v1",
            "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(),
            "changed_tables": sorted(changed),
            "changes": changes,
            "unchanged_parent_tables": len(before) - len(changed)}


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode()
    if write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
