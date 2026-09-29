"""A17 two-unit candidate source identity and parent/graph invariants."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
LIB = ROOT / "cases/simlox-air-support"
CASE = LIB / "A17-multi-unit-group-v1.0.0"
spec = importlib.util.spec_from_file_location("simlox_a17_v100_build", CASE / "build.py")
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
check_spec = importlib.util.spec_from_file_location("simlox_a17_v100_probe_check", CASE / "check_probe.py")
assert check_spec and check_spec.loader
probe_check = importlib.util.module_from_spec(check_spec)
check_spec.loader.exec_module(probe_check)


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def by_name(doc: dict) -> dict[str, dict]:
    return {table["name"]: table for table in doc["model"]["tables"]}


def records(table: dict) -> list[dict]:
    cols = [col["name"] for col in table["columns"]]
    return [dict(zip(cols, row)) for instance in table["instances"] for row in instance["rows"]]


def test_frozen_parent_child_and_exact_declared_diff() -> None:
    contract = read(CASE / "contract.json")
    parent_path = LIB / "A03-two-aircraft-formation-v1.0.1/native-input.json"
    child_path = CASE / "native-input.json"
    parent = read(parent_path)
    child = read(child_path)
    diff = read(CASE / "parent-diff.json")
    assert hashlib.sha256(parent_path.read_bytes()).hexdigest() == contract["parent"]["input_sha256"]
    assert hashlib.sha256(child_path.read_bytes()).hexdigest() == contract["native_input_sha256"]
    assert builder.build() == child
    assert set(by_name(child)) - set(by_name(parent)) == {"UnitGroup", "UnitGroupMember"}
    changed = {name for name in set(by_name(parent)) | set(by_name(child)) if by_name(parent).get(name) != by_name(child).get(name)}
    assert changed == set(contract["delta"]["tables"]) == set(diff["changed_tables"])
    for name in changed:
        assert diff["changed_tables"][name] == {
            "before_rows": records(by_name(parent)[name]) if name in by_name(parent) else None,
            "after_rows": records(by_name(child)[name]),
        }


def test_group_graph_and_hand_count_are_closed() -> None:
    tables = by_name(read(CASE / "native-input.json"))
    stations = {r["STID"] for r in records(tables["Station"])}
    units = {r["UNID"]: r["STID"] for r in records(tables["Unit"])}
    groups = {r["UGID"] for r in records(tables["UnitGroup"])}
    members = records(tables["UnitGroupMember"])
    deployments = records(tables["SystemDeployment"])
    operations = records(tables["Operations"])
    assert stations == {"BASE-01", "BASE-02"}
    assert units == {"TEACH-UNIT": "BASE-01", "TEACH-UNIT-2": "BASE-02"}
    assert all(station in stations for station in units.values())
    assert groups == {"TEACH-GROUP"}
    assert [(r["USTID"], r["PRI"], r["XTIME"]) for r in members] == [
        ("TEACH-UNIT", 1, 0), ("TEACH-UNIT-2", 2, 0),
    ]
    assert all(r["UGID"] in groups and r["USTID"] in units for r in members)
    assert all(r["USTID"] in units and r["USTID"] not in groups for r in deployments)
    assert sum(r["QTYPS"] for r in deployments) == 2
    assert [(r["USTID"], r["PRID"]) for r in operations] == [("TEACH-GROUP", "BASIC-SCHEDULE")]
    mission = records(tables["MissionType"])
    assert len(mission) == 1 and (mission[0]["NOS"], mission[0]["MNOS"]) == (2, 2)


def test_generator_rejects_tampered_parent_and_unknown_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    altered = copy.deepcopy(read(builder.PARENT))
    altered["model"]["tables"][0]["name"] = "TAMPERED"
    path = tmp_path / "altered-parent.json"
    path.write_text(json.dumps(altered), encoding="utf-8")
    monkeypatch.setattr(builder, "PARENT", path)
    with pytest.raises(ValueError, match="fingerprint"):
        builder.build()
    with pytest.raises(ValueError, match="unknown columns"):
        builder.row(by_name(read(CASE / "native-input.json"))["UnitGroup"], BAD_FIELD=1)


def test_probe_check_detects_changed_group_rows_and_incomplete_logs(tmp_path: Path) -> None:
    source = (CASE / "native-input.json").read_bytes()
    (tmp_path / "input.json").write_bytes(source)
    (tmp_path / "roundtrip-raw.json").write_bytes(source)
    (tmp_path / "model.sxi").write_bytes(b"test-model")
    (tmp_path / "import.log").write_text("Import completed!", encoding="utf-8")
    (tmp_path / "export.log").write_text("Export completed!", encoding="utf-8")
    assert probe_check.validate(tmp_path)["passed"]

    altered = read(tmp_path / "roundtrip-raw.json")
    by_name(altered)["UnitGroupMember"]["instances"][0]["rows"][1][0] = "DIFFERENT-GROUP"
    (tmp_path / "roundtrip-raw.json").write_text(json.dumps(altered), encoding="utf-8")
    (tmp_path / "export.log").write_text("Export started", encoding="utf-8")
    differences = probe_check.validate(tmp_path)["differences"]
    assert any("UnitGroupMember" in issue for issue in differences)
    assert "export completion marker absent" in differences
