"""Assert exact endpoint and zero-initiation changes against each parent."""
from __future__ import annotations

import copy
import json

from build import ARMS, HERE, build, sha

CHANGED = {"Control", "ResultCollection", "OperationProfile", "ProblemDescription"}


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def check(arm: str) -> dict:
    parent_path, _, horizon, _ = ARMS[arm]
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    child = json.loads((HERE / f"{arm}-input.json").read_text(encoding="utf-8"))
    assert child == build(arm)
    original = tables(parent)
    current = tables(child)
    assert original.keys() == current.keys()
    assert len(original) == 32
    assert all(original[name] == current[name] for name in original.keys() - CHANGED)
    assert parent.keys() == child.keys()
    outer_parent = copy.deepcopy(parent)
    outer_child = copy.deepcopy(child)
    outer_parent["model"]["tables"] = []
    outer_child["model"]["tables"] = []
    assert outer_parent == outer_child

    expected = copy.deepcopy(parent)
    t = tables(expected)
    control = t["Control"]["instances"][0]["rows"][0]
    assert (control[1], control[6]) == (36.0, 36.0)
    control[1] = control[6] = horizon
    collection = t["ResultCollection"]["instances"][0]["rows"]
    assert [r[3] for r in collection] == [36.0, 36.0, 36.0]
    for row in collection:
        row[3] = horizon
    profile = t["OperationProfile"]["instances"][0]["rows"]
    assert [r[2] for r in profile] == [8.0, 20.0, 32.0]
    assert [r[4] for r in profile] == [1, 1, 1]
    profile[0][2] = 0.0
    profile[0][4] = 0
    t["OperationProfile"]["instances"][0]["rows"] = profile[:1]
    t["ProblemDescription"]["instances"][0]["rows"] = current["ProblemDescription"]["instances"][0]["rows"]
    assert expected == child
    assert set(name for name in original if original[name] != current[name]) == CHANGED
    return {
        "parent_sha256": sha(parent_path),
        "input_sha256": sha(HERE / f"{arm}-input.json"),
        "changed_tables": sorted(CHANGED),
        "control_endpoint_hours": [36.0, horizon],
        "result_collection_endpoint_hours": [[36.0, horizon]] * 3,
        "operation_profile_before": original["OperationProfile"]["instances"][0]["rows"],
        "operation_profile_after": current["OperationProfile"]["instances"][0]["rows"],
        "other_tables_identical": len(original) - len(CHANGED),
    }


if __name__ == "__main__":
    result = {arm: check(arm) for arm in ARMS}
    target = HERE / "exact-diff.json"
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if target.exists():
        assert target.read_text(encoding="utf-8") == raw
    else:
        target.write_text(raw, encoding="utf-8")
    print(target)
