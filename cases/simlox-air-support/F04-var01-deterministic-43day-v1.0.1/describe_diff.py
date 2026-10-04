"""Freeze the bounded F03→F04 source-cell delta."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, build


def main() -> None:
    parent, child = json.loads(PARENT.read_bytes()), build()
    a = {t["name"]: t for t in parent["model"]["tables"]}
    b = {t["name"]: t for t in child["model"]["tables"]}
    assert list(a) == list(b)
    changes = []
    for name, old in a.items():
        new = b[name]
        assert old["columns"] == new["columns"]
        assert len(old["instances"]) == len(new["instances"]) == 1
        before, after = old["instances"][0]["rows"], new["instances"][0]["rows"]
        assert len(before) == len(after)
        for ri, (row1, row2) in enumerate(zip(before, after), start=1):
            for ci, (v1, v2) in enumerate(zip(row1, row2)):
                if v1 != v2:
                    changes.append({"table": name, "row": ri,
                                    "column": old["columns"][ci]["name"],
                                    "from": v1, "to": v2})
    expected = {
        ("ProblemDescription", "PDESC"): 1,
        ("Control", "SIMPE"): 1, ("Control", "RCEND"): 1,
        ("System", "FRT"): 1,
        ("Item", "FRT"): 2,
        ("SystemDeployment", "QTYPS"): 2,
        ("OperationProfile", "IQTY"): 2,
        ("OperationProfile", "IPER"): 2,
        ("ResultCollection", "RCEND"): 2,
    }
    observed = {}
    for c in changes:
        key = (c["table"], c["column"])
        observed[key] = observed.get(key, 0) + 1
    assert observed == expected, (observed, expected)
    result = {"schema": "simlox-f04-deterministic-43day-exact-diff/v1",
              "parent": "accepted F03.var01 staffed 2+1 fleet",
              "changes": changes,
              "unchanged": "all other tables and cells including mission type, base resources, PM, supply network, repair and seed"}
    raw = (json.dumps(result, indent=2) + "\n").encode()
    target = HERE / "exact-diff.json"
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
