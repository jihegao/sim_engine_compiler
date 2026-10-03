"""Check exact source deltas for both E11.var02 boundary arms."""
from __future__ import annotations

import hashlib
import json
import sys

from build import ARMS, HERE, PARENT, PARENT_SHA, build

OUTPUT = HERE / "exact-diff.json"


def changes(before: dict, after: dict) -> list[dict]:
    old = {t["name"]: t for t in before["model"]["tables"]}
    new = {t["name"]: t for t in after["model"]["tables"]}
    assert set(old) == set(new)
    assert {n for n in old if old[n] != new[n]} == {"ProblemDescription", "TransportPolicyProfile"}
    result = []
    for name in sorted(old):
        a, b = old[name], new[name]
        assert a["columns"] == b["columns"] and len(a["instances"]) == len(b["instances"]) == 1
        rows_a, rows_b = a["instances"][0]["rows"], b["instances"][0]["rows"]
        assert len(rows_a) == len(rows_b)
        columns = [c["name"] for c in a["columns"]]
        for ri, (ar, br) in enumerate(zip(rows_a, rows_b)):
            for ci, (x, y) in enumerate(zip(ar, br)):
                if x != y:
                    result.append({"table": name, "row": ri, "column": columns[ci], "before": x, "after": y})
    assert [(x["table"], x["row"], x["column"]) for x in result] == [
        ("ProblemDescription", 0, "PDESC"), ("TransportPolicyProfile", 0, "DURN"),
        ("TransportPolicyProfile", 1, "STIM"), ("TransportPolicyProfile", 1, "DURN")
    ]
    return result


def describe() -> dict:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    parent = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    result = {"schema": "simlox-e11-var02-isolation-boundary-exact-diff/v1",
              "parent_sha256": PARENT_SHA, "arms": {}, "unchanged_parent_tables": 30}
    for arm in ARMS:
        raw = build(arm)
        result["arms"][arm] = {"source_sha256": hashlib.sha256(raw).hexdigest(),
                                "changes": changes(parent, json.loads(raw))}
    return result


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
