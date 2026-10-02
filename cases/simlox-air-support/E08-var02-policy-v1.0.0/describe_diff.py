"""Verify the exact rule-only deltas from accepted E08 IMMEDIATE."""
import hashlib
import json
from pathlib import Path
from build import HERE, PARENT, PARENT_SHA, POLICIES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {t["name"]: t for t in doc["model"]["tables"]}


def field_delta(before, after):
    assert before["columns"] == after["columns"]
    assert len(before["instances"]) == len(after["instances"]) == 1
    old, new = before["instances"][0]["rows"], after["instances"][0]["rows"]
    assert len(old) == len(new) == 1
    names = [c["name"] for c in before["columns"]]
    return [(names[i], a, b) for i, (a, b) in enumerate(zip(old[0], new[0])) if a != b]


def main():
    assert sha(PARENT) == PARENT_SHA
    base = tables(PARENT)
    result = {"schema": "simlox-e08-var02-lsrul-exact-diff/v1", "parent_sha256": PARENT_SHA, "children": {}}
    for policy in POLICIES:
        path = HERE / f"{policy}-input.json"
        child = tables(path)
        assert set(base) == set(child)
        changed = sorted(name for name in base if base[name] != child[name])
        assert changed == ["LateralSupport", "ProblemDescription"], changed
        lateral = field_delta(base["LateralSupport"], child["LateralSupport"])
        description = field_delta(base["ProblemDescription"], child["ProblemDescription"])
        assert lateral == [("LSRUL", "IMMEDIATE", policy.upper())]
        assert len(description) == 1 and description[0][0] == "PDESC"
        result["children"][policy] = {"source_sha256": sha(path), "changed_tables": changed,
                                      "unchanged_table_count": len(base) - 2,
                                      "lateral_delta": lateral, "description_delta": description}
    encoded = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    out = HERE / "exact-diff.json"
    if out.exists():
        assert out.read_bytes() == encoded, "frozen exact diff differs"
    else:
        out.write_bytes(encoded)
    print(json.dumps({"exact_diff_sha256": sha(out), "child_sha256": {p: sha(HERE / f"{p}-input.json") for p in POLICIES}}))


if __name__ == "__main__":
    main()
