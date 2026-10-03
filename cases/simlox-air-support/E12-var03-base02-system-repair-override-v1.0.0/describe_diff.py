"""Verify the exact station override delta from accepted E12.var02 two-fault group."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    before = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    after = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(before) == set(after) and len(before) == 32
    changed = sorted(name for name in before if before[name] != after[name])
    assert changed == ["ProblemDescription", "SystemRepair", "TaskBreakDown", "Tasks"]
    for name in changed:
        assert before[name]["columns"] == after[name]["columns"]
        assert len(before[name]["instances"]) == len(after[name]["instances"]) == 1
    assert len(after["SystemRepair"]["instances"][0]["rows"]) == 2
    assert len(after["Tasks"]["instances"][0]["rows"]) == 2
    assert len(after["TaskBreakDown"]["instances"][0]["rows"]) == 4
    changes = []
    for name in changed:
        a, b = before[name]["instances"][0]["rows"], after[name]["instances"][0]["rows"]
        assert b[: len(a)] == a if name != "ProblemDescription" else len(a) == len(b) == 1
        changes.append({"table": name, "before_rows": len(a), "after_rows": len(b), "added_rows": b[len(a):] if name != "ProblemDescription" else [],
                        "description_before": a[0][0] if name == "ProblemDescription" else None,
                        "description_after": b[0][0] if name == "ProblemDescription" else None})
    return {"schema": "simlox-e12-var03-base02-system-repair-override-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": changed,
            "unchanged_parent_tables": len(before) - len(changed), "changes": changes}


if __name__ == "__main__":
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if sys.argv[1:] == ["--write"]:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: describe_diff.py [--write]")
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())
