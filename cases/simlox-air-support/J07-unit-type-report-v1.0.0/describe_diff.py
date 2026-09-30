"""Verify the exact A17-to-J07 source-table delta."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
CHILD_SHA = "5609881f54c47c024b1b41f338bf0dd0e04e20e49a41d42b1a81642bdab54f55"


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(CHILD.read_bytes()).hexdigest() == CHILD_SHA
    before, after = tables(PARENT), tables(CHILD)
    assert before.keys() == after.keys()
    changed = {name: {"before": before[name]["instances"][0]["rows"], "after": after[name]["instances"][0]["rows"]} for name in before if before[name] != after[name]}
    assert set(changed) == {"MissionType", "OperationProfile", "Operations", "ProblemDescription"}
    result = {"schema": "simlox-j07-unit-type-report-exact-diff/v1", "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA, "changed_tables": changed}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_text(encoding="utf-8") == raw
    else:
        path.write_text(raw, encoding="utf-8")
    print(json.dumps({"changed_tables": list(changed), "diff_sha256": hashlib.sha256(raw.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
