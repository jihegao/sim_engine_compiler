"""Verify the exact E12.var01 to group-repair default delta."""
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
    assert changed == ["ProblemDescription", "Station", "SystemRepair"]
    for name in changed:
        assert before[name]["columns"] == after[name]["columns"]
    sr, tr = (x["Station"]["instances"][0]["rows"] for x in (before, after))
    scols = [c["name"] for c in before["Station"]["columns"]]
    g = scols.index("GSTID")
    assert len(sr) == len(tr) == 3 and [r[g] for r in sr] == [None, None, None] and [r[g] for r in tr] == ["BASE-GRP", "BASE-GRP", None]
    assert all(a[:g] + a[g + 1:] == b[:g] + b[g + 1:] for a, b in zip(sr, tr))
    rr, ur = (x["SystemRepair"]["instances"][0]["rows"] for x in (before, after))
    rcols = [c["name"] for c in before["SystemRepair"]["columns"]]
    assert len(rr) == 2 and len(ur) == 1 and [r[rcols.index("STID")] for r in rr] == ["BASE-01", "BASE-02"] and ur[0][rcols.index("STID")] == "BASE-GRP"
    assert rr[0][2:] == rr[1][2:] == ur[0][2:]
    return {"schema": "simlox-e12-var02-group-repair-exact-diff/v1", "parent_sha256": PARENT_SHA,
            "source_sha256": hashlib.sha256(build()).hexdigest(), "changed_tables": changed,
            "unchanged_parent_tables": len(before) - len(changed),
            "description_before": before["ProblemDescription"]["instances"][0]["rows"][0][0],
            "description_after": after["ProblemDescription"]["instances"][0]["rows"][0][0],
            "station_gstid_before": [r[g] for r in sr], "station_gstid_after": [r[g] for r in tr],
            "repair_columns": rcols, "repair_rows_before": rr, "repair_rows_after": ur}


if __name__ == "__main__":
    raw = (json.dumps(describe(), ensure_ascii=False, indent=2) + "\n").encode()
    if sys.argv[1:] == ["--write"]:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif sys.argv[1:]:
        raise SystemExit("usage: describe_diff.py [--write]")
    else:
        assert OUTPUT.read_bytes() == raw
    print(hashlib.sha256(raw).hexdigest())
