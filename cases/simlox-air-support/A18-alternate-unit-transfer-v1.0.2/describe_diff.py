"""Check A17 lineage and isolated A18 AlternateUnit row."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
CONFIGURED = HERE / "configured-input.json"
ABSENT = HERE / "absent-input.json"
HASHES = {
    "parent": "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974",
    "configured": "0cc2a25c572e9b2f4f1f3054ef139ebfbb749324318d0302d5e99fcfc36c859a",
    "absent": "eaae8621e88a74fc6ed800ab04b87a623f85623c0401c4c2db34ea5eb96d57d3",
}


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8-sig"))["model"]["tables"]}


def delta(before: dict, after: dict) -> dict:
    return {name: {"before": before.get(name), "after": after.get(name)} for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}


def main() -> None:
    for name, path in (("parent", PARENT), ("configured", CONFIGURED), ("absent", ABSENT)):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name]
    parent, configured, absent = tables(PARENT), tables(CONFIGURED), tables(ABSENT)
    parent_delta = delta(parent, configured)
    control_delta = delta(absent, configured)
    assert set(parent_delta) == {"ProblemDescription", "Control", "SystemDeployment", "Unit", "Operations", "OperationProfile", "UnitGroup", "UnitGroupMember", "AlternateUnit"}
    assert set(control_delta) == {"ProblemDescription", "AlternateUnit"}
    result = {"schema": "simlox-a18-alternate-unit-v102-exact-diff/v1", "source_sha256": HASHES, "a17_to_configured": parent_delta, "absent_to_configured": control_delta}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    output = HERE / "exact-diff.json"
    if output.exists():
        assert output.read_text(encoding="utf-8") == raw
    else:
        output.write_text(raw, encoding="utf-8")
    print(json.dumps({"a17_changed_tables": sorted(parent_delta), "control_changed_tables": sorted(control_delta), "diff_sha256": hashlib.sha256(raw.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
