"""Check A17 lineage and the isolated A18 ENALU switch."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0" / "native-input.json"
ENABLED = HERE / "enabled-input.json"
DISABLED = HERE / "disabled-input.json"
HASHES = {
    "parent": "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974",
    "enabled": "c2837b5aa5a191b8a2e0c4b3c5e1cbf450cacd9fc211bb03b5bc6d8c1c7eae99",
    "disabled": "ee3cfbb25f13851269b65073ff7c92ae9caeec37502e9431bb91a87764f39960",
}


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_text(encoding="utf-8-sig"))["model"]["tables"]}


def delta(before: dict, after: dict) -> dict:
    return {name: {"before": before.get(name), "after": after.get(name)} for name in sorted(before.keys() | after.keys()) if before.get(name) != after.get(name)}


def main() -> None:
    for name, path in (("parent", PARENT), ("enabled", ENABLED), ("disabled", DISABLED)):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == HASHES[name]
    parent, enabled, disabled = tables(PARENT), tables(ENABLED), tables(DISABLED)
    parent_delta = delta(parent, enabled)
    control_delta = delta(disabled, enabled)
    assert set(parent_delta) == {"ProblemDescription", "Control", "SystemDeployment", "Unit", "Operations", "OperationProfile", "UnitGroup", "UnitGroupMember", "AlternateUnit"}
    assert set(control_delta) == {"ProblemDescription", "Control"}
    result = {"schema": "simlox-a18-alternate-unit-v101-exact-diff/v1", "source_sha256": HASHES, "a17_to_enabled": parent_delta, "disabled_to_enabled": control_delta}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    output = HERE / "exact-diff.json"
    if output.exists():
        assert output.read_text(encoding="utf-8") == raw
    else:
        output.write_text(raw, encoding="utf-8")
    print(json.dumps({"a17_changed_tables": sorted(parent_delta), "control_changed_tables": sorted(control_delta), "diff_sha256": hashlib.sha256(raw.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
