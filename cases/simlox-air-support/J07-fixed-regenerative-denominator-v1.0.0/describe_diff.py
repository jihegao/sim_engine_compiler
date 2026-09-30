"""Check the exact accepted A07 to mixed J07 source delta."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A07-regenerative-relief-v1.0.0" / "native-input.json"
CHILD = HERE / "native-input.json"
PARENT_SHA = "fed4f8343d203fc250d8b3508f3f5f9fe76ecbd1a86646d5965531d246b89240"
CHILD_SHA = "0b98b8c6816a0923113c1b9e77c5af5493c93104b2bd0dc06bb6552533c1fc3e"


def table_map(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8"))["model"]["tables"]}


def main() -> None:
    assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA
    assert hashlib.sha256(CHILD.read_bytes()).hexdigest() == CHILD_SHA
    before, after = table_map(PARENT), table_map(CHILD)
    assert before.keys() == after.keys()
    changed = {name: {"before": before[name]["instances"][0]["rows"], "after": after[name]["instances"][0]["rows"]} for name in before if before[name] != after[name]}
    assert set(changed) == {"ProblemDescription", "MissionType", "OperationProfile"}
    result = {"schema": "simlox-j07-fixed-regenerative-exact-diff/v1", "parent_sha256": PARENT_SHA, "child_sha256": CHILD_SHA, "changed_tables": changed}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    path = HERE / "exact-diff.json"
    if path.exists():
        assert path.read_text(encoding="utf-8") == raw
    else:
        path.write_text(raw, encoding="utf-8")
    print(json.dumps({"changed_tables": list(changed), "diff_sha256": hashlib.sha256(raw.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
