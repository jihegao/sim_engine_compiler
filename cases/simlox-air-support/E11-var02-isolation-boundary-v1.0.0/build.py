"""Freeze demand-before and demand-at autonomous isolation boundaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E11-autonomous-support-gap-v1.0.0/native-input.json"
PARENT_SHA = "d1fc66999c081acb6f29e58e5083cee58c317f0c3e0597587037efcb58a2cfd3"
ARMS = {"before": (11.0, 13.0, 23.0), "at": (10.0, 12.0, 24.0)}


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def build(arm: str) -> bytes:
    assert arm in ARMS
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    gap_start, restart, second_duration = ARMS[arm]
    table(doc, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        f"E11.var02 h10 demand {arm} isolation h{gap_start:g}-{restart:g}"
    )
    profile = table(doc, "TransportPolicyProfile")
    rows = profile["instances"][0]["rows"]
    assert [(r[1], r[2], r[5]) for r in rows] == [
        ("ONDEM", 0.0, 9.0), ("ONDEM", 11.0, 25.0)
    ]
    rows[0][5] = gap_start
    rows[1][2] = restart
    rows[1][5] = second_duration
    assert restart + second_duration == 36.0
    return (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()


def main() -> None:
    write = len(sys.argv) == 2 and sys.argv[1] == "--write"
    assert len(sys.argv) == 1 or write
    result = {}
    for arm in ARMS:
        path = HERE / f"native-input-{arm}.json"
        raw = build(arm)
        if write:
            if path.exists():
                raise FileExistsError(path)
            path.write_bytes(raw)
        else:
            assert path.read_bytes() == raw
        result[arm] = hashlib.sha256(raw).hexdigest()
    print(json.dumps({"parent_sha256": PARENT_SHA, "arms_sha256": result}))


if __name__ == "__main__":
    main()
