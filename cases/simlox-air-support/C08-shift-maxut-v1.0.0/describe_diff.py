"""Freeze the precise C07 parent-to-C08 input delta."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-repeat-nested-v1.0.0" / "explicit-input.json"
CHILD = HERE / "maxut-one-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    a = {t["name"]: t for t in json.loads(PARENT.read_bytes())["model"]["tables"]}
    b = {t["name"]: t for t in json.loads(CHILD.read_bytes())["model"]["tables"]}
    assert a.keys() == b.keys()
    changed = sorted(n for n in a if a[n] != b[n])
    assert changed == ["ProblemDescription", "ShiftResource"]
    for n in changed:
        assert a[n]["columns"] == b[n]["columns"]
        assert len(a[n]["instances"]) == len(b[n]["instances"]) == 1
    assert a["ShiftResource"]["instances"][0]["rows"][0][:4] == b["ShiftResource"]["instances"][0]["rows"][0][:4]
    assert a["ShiftResource"]["instances"][0]["rows"][0][4:] == [None, None]
    assert b["ShiftResource"]["instances"][0]["rows"][0][4:] == [1.0, None]
    result = {
        "schema": "simlox-c08-shift-maxut-exact-diff/v1",
        "parent": str(PARENT.relative_to(HERE.parent)),
        "parent_sha256": sha(PARENT),
        "child_sha256": sha(CHILD),
        "changed_tables": changed,
        "business_change": "ShiftResource.MAXUT unset to 1.0 hour per P-CREW in DAY-OPEN at BASE-01; nominal and active quantity remain two",
        "provenance_change": "ProblemDescription only",
        "unchanged_table_count": len(a) - len(changed),
    }
    path = HERE / "exact-diff.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()
