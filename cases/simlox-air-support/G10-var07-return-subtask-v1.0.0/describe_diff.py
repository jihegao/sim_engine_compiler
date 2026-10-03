"""Verify the controlled crew-capacity pair and its G10.var06 parent delta."""
from __future__ import annotations

import hashlib
import json

from build import HERE, PARENT, PARENT_SHA, sha


def tables(path):
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def changes(before, after):
    return sorted(name for name in before.keys() & after.keys() if before[name] != after[name])


def main() -> None:
    if sha(PARENT.read_bytes()) != PARENT_SHA:
        raise ValueError("parent hash differs")
    parent = tables(PARENT)
    present_path = HERE / "native-input-crew-present.json"
    absent_path = HERE / "native-input-crew-absent.json"
    present, absent = tables(present_path), tables(absent_path)
    parent_changed = changes(parent, present)
    pair_changed = changes(present, absent)
    expected_parent = ["MissionType", "OperationProfile", "ProblemDescription", "Resource", "ResourceAllocation", "SubTaskResource", "SystemRepair", "TaskBreakDown"]
    if set(parent) != set(present) or set(present) != set(absent) or parent_changed != expected_parent or pair_changed != ["ProblemDescription", "ResourceAllocation"]:
        raise ValueError(f"unexpected table delta: parent={parent_changed}, pair={pair_changed}")
    palloc, aalloc = (next(t for t in doc.values() if t["name"] == "ResourceAllocation") for doc in (present, absent))
    cols = [c["name"] for c in palloc["columns"]]
    prows = palloc["instances"][0]["rows"]
    arows = aalloc["instances"][0]["rows"]
    if len(prows) != 1 or len(arows) != 1 or prows[0][cols.index("RQTY")] != 1 or arows[0][cols.index("RQTY")] != 0:
        raise ValueError("crew quantity pair differs")
    out = {
        "schema": "simlox-g10-var07-v100-paired-diff/v1",
        "parent_sha256": PARENT_SHA,
        "crew_present_sha256": sha(present_path.read_bytes()),
        "crew_absent_sha256": sha(absent_path.read_bytes()),
        "parent_changed_tables": parent_changed,
        "pair_changed_tables": pair_changed,
        "parent_changes": {name: {"before": parent[name]["instances"][0]["rows"], "after": present[name]["instances"][0]["rows"]} for name in parent_changed},
        "pair_changes": {name: {"before": present[name]["instances"][0]["rows"], "after": absent[name]["instances"][0]["rows"]} for name in pair_changed},
    }
    path = HERE / "exact-diff.json"
    raw = (json.dumps(out, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        path.write_bytes(raw)
    print(json.dumps({"parent_changed_tables": parent_changed, "pair_changed_tables": pair_changed, "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
