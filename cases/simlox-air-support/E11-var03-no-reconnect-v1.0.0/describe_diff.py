"""Check exact E11 base to no-reconnection source delta."""
from __future__ import annotations

import hashlib
import json
import sys

from build import HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def describe() -> dict:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    a = {t["name"]: t for t in json.loads(PARENT.read_text(encoding="utf-8-sig"))["model"]["tables"]}
    b = {t["name"]: t for t in json.loads(build())["model"]["tables"]}
    assert set(a) == set(b)
    assert {n for n in a if a[n] != b[n]} == {"ProblemDescription", "TransportPolicyProfile"}
    old, new = a["TransportPolicyProfile"], b["TransportPolicyProfile"]
    assert old["columns"] == new["columns"] and len(old["instances"]) == len(new["instances"]) == 1
    old_rows, new_rows = old["instances"][0]["rows"], new["instances"][0]["rows"]
    assert len(old_rows) == 2 and new_rows == old_rows[:1]
    assert a["ProblemDescription"]["columns"] == b["ProblemDescription"]["columns"]
    assert len(a["ProblemDescription"]["instances"][0]["rows"]) == len(b["ProblemDescription"]["instances"][0]["rows"]) == 1
    return {"schema": "simlox-e11-var03-no-reconnect-exact-diff/v1",
            "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(),
            "changed_tables": ["ProblemDescription", "TransportPolicyProfile"],
            "description_before": a["ProblemDescription"]["instances"][0]["rows"][0][0],
            "description_after": b["ProblemDescription"]["instances"][0]["rows"][0][0],
            "retained_policy_row": new_rows[0],
            "deleted_policy_row": old_rows[1],
            "unchanged_parent_tables": len(a) - 2}


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
