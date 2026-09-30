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
    "enabled": "2b1fe62f253cb5f3333cc1620737f892e2bd0f2e2fcf52e3197ed9d22db4995e",
    "disabled": "6a461d5642e5234e71e316915d68ec365069e9358d5545629a54b7f6bb35a9a9",
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
    assert set(parent_delta) == {"ProblemDescription", "Control", "SystemDeployment", "Unit", "Operations", "UnitGroup", "UnitGroupMember", "AlternateUnit"}
    assert set(control_delta) == {"ProblemDescription", "Control"}
    result = {"schema": "simlox-a18-alternate-unit-exact-diff/v1", "source_sha256": HASHES, "a17_to_enabled": parent_delta, "disabled_to_enabled": control_delta}
    raw = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    output = HERE / "exact-diff.json"
    if output.exists():
        assert output.read_text(encoding="utf-8") == raw
    else:
        output.write_text(raw, encoding="utf-8")
    print(json.dumps({"a17_changed_tables": sorted(parent_delta), "control_changed_tables": sorted(control_delta), "diff_sha256": hashlib.sha256(raw.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
