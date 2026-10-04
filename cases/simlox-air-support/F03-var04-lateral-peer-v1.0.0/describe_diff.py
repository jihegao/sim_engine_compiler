"""Freeze integrated lateral-peer additions and ENLAT-only business pair switch."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, build, rows, table


def main() -> None:
    parent = json.loads(PARENT.read_bytes())
    on, off = build()
    old, a, b = ({t["name"]: t for t in d["model"]["tables"]} for d in (parent, on, off))
    assert len(old) == 32 and len(a) == len(b) == 33
    assert list(a) == list(b) == list(old) + ["LateralSupport"]
    changed = [n for n in old if old[n] != a[n]]
    paired = [n for n in a if a[n] != b[n]]
    assert changed == ["ProblemDescription", "Control", "Station", "StockAllocation"] and paired == ["ProblemDescription", "Control"]
    assert rows(on, "Control")[0][8] == "Y" and rows(off, "Control")[0][8] == "N"
    assert rows(on, "Control")[0][:8] == rows(off, "Control")[0][:8] and rows(on, "Control")[0][9:] == rows(off, "Control")[0][9:]
    assert [(r[0], r[8]) for r in rows(on, "Station")] == [("BASE-01", "LAT-01"), ("DEPOT-01", None), ("BASE-02", "LAT-01")]
    assert rows(on, "StockAllocation")[-1][:4] == ["AIR_BASIC", "TEACH-LRU-01", "BASE-02", 1]
    assert rows(on, "LateralSupport") == [["LAT-01", 0.5, "N", "IMMEDIATE", None]]
    result = {"schema": "simlox-f03-lateral-peer-exact-diff/v1", "parent_changed_tables": changed,
              "parent_appended_tables": ["LateralSupport"], "pair_changed_tables": paired,
              "sole_business_pair_change": {"table": "Control", "row": 1, "column": "ENLAT", "lateral_on": "Y", "lateral_off": "N"},
              "parent_other_tables": "unchanged including unit deployments, missions, schedules, depot routes, repair, PM and worker resources",
              "geometry": "BASE-01 and BASE-02 LAT-01 peers, BASE-02 one opening LRU, TLAT0.5h IMMEDIATE/DLAYL=N, each base two-hour depot route"}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
