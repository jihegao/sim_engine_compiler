"""Check the entire four-input parent/contrast topology and emit exact differences."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import HERE, PARENT_DIR, PARENTS, VARIANTS, table


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tabmap(doc: dict) -> dict:
    tables = doc["model"]["tables"]
    names = [t["name"] for t in tables]
    assert len(names) == len(set(names))
    return {t["name"]: t for t in tables}


def main() -> None:
    result = {"schema": "simlox-a15-partial-dependency-abort-exact-diff/v1", "variants": {}}
    children = {}
    for variant in VARIANTS:
        mode, rate = variant.split("-")
        parent_name, parent_sha = PARENTS[mode]
        parent_bytes = (PARENT_DIR / parent_name).read_bytes()
        assert sha(parent_bytes) == parent_sha
        parent = json.loads(parent_bytes)
        child_bytes = (HERE / f"{variant}-input.json").read_bytes()
        child = json.loads(child_bytes)
        assert {k: v for k, v in child.items() if k != "model"} == {k: v for k, v in parent.items() if k != "model"}
        assert {k: v for k, v in child["model"].items() if k != "tables"} == {k: v for k, v in parent["model"].items() if k != "tables"}
        old, new = tabmap(parent), tabmap(child)
        assert set(new) - set(old) == {"MissionTypeUtilization"}
        assert not set(old) - set(new)
        changed = sorted(n for n in old if old[n] != new[n])
        assert changed == ["OperationParameter", "ProblemDescription"]
        assert [c["name"] for c in new["MissionTypeUtilization"]["columns"]] == ["MTID", "SID", "OPID", "UTIL", "UTILU", "NOTE"]
        assert len(new["MissionTypeUtilization"]["instances"][0]["rows"]) == 1
        assert len(new) == len(old) + 1
        result["variants"][variant] = {
            "parent": parent_name, "parent_sha256": parent_sha, "input_sha256": sha(child_bytes),
            "parent_table_count": len(old), "child_table_count": len(new),
            "modified_parent_tables": changed, "added_tables": ["MissionTypeUtilization"],
            "description": table(child, "ProblemDescription")["instances"][0]["rows"],
            "operation_parameter": table(child, "OperationParameter")["instances"][0]["rows"],
            "utilization": new["MissionTypeUtilization"]["instances"][0]["rows"],
        }
        children[variant] = child
    for mode in PARENTS:
        a, b = tabmap(children[f"{mode}-hour"]), tabmap(children[f"{mode}-mission"])
        assert sorted(n for n in a if a[n] != b[n]) == ["MissionTypeUtilization", "ProblemDescription"]
    for rate in ("hour", "mission"):
        a, b = tabmap(children[f"control-{rate}"]), tabmap(children[f"dependent-{rate}"])
        assert set(b) - set(a) == {"MissionDependence"}
        assert not set(a) - set(b)
        assert sorted(n for n in a if a[n] != b[n]) == ["ProblemDescription"]
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(raw))


if __name__ == "__main__":
    main()
