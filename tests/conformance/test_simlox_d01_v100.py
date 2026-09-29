"""D01 direct-system-repair candidate identity and negative controls."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "cases/simlox-air-support"
CASE = CASES / "D01-system-direct-repair-v1.0.0"
spec = importlib.util.spec_from_file_location("simlox_d01_v100_build", CASE / "build.py")
assert spec and spec.loader
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
checker_spec = importlib.util.spec_from_file_location("simlox_d01_v100_roundtrip", CASE / "check_roundtrip.py")
assert checker_spec and checker_spec.loader
checker = importlib.util.module_from_spec(checker_spec)
checker_spec.loader.exec_module(checker)


def read(path: Path) -> dict:
    return json.loads(path.read_bytes())


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1
    return found[0]


def records(t: dict) -> list[dict]:
    columns = [x["name"] for x in t["columns"]]
    return [dict(zip(columns, r)) for instance in t["instances"] for r in instance["rows"]]


def test_frozen_model_and_exact_parent_delta() -> None:
    contract = read(CASE / "contract.json")
    parent = read(builder.PARENT)
    child = read(CASE / "native-input.json")
    diff = read(CASE / "parent-diff.json")
    assert hashlib.sha256(builder.PARENT.read_bytes()).hexdigest() == contract["parent"]["input_sha256"]
    assert hashlib.sha256((CASE / "native-input.json").read_bytes()).hexdigest() == contract["native_input_sha256"]
    assert builder.build() == child
    changed = {name for name in (t["name"] for t in child["model"]["tables"]) if table(parent, name) != table(child, name)}
    assert changed == set(contract["delta"]["tables"]) == set(diff["changed_tables"])
    for name in changed:
        assert diff["changed_tables"][name] == {
            "before_rows": records(table(parent, name)),
            "after_rows": records(table(child, name)),
        }


def test_direct_failure_configuration_and_parent_missions() -> None:
    parent = read(builder.PARENT)
    child = read(CASE / "native-input.json")
    system = records(table(child, "System"))
    repair = records(table(child, "SystemRepair"))
    assert [(r["SID"], r["FRT"], r["OPID"]) for r in system] == [("TEACH-AIR-01", 300000, "OPHOURS")]
    assert len(repair) == 1
    assert (repair[0]["SID"], repair[0]["STID"], repair[0]["DIRPT"], repair[0]["DIRPF"]) == ("TEACH-AIR-01", "BASE-01", 0.5, 1.0)
    assert records(table(child, "Item")) == []
    assert records(table(child, "ItemStructure")) == []
    assert records(table(child, "OperationProfile")) == records(table(parent, "OperationProfile"))
    assert records(table(child, "Control")) == records(table(parent, "Control"))


def test_parent_tamper_and_roundtrip_row_corruption_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    altered = copy.deepcopy(read(builder.PARENT))
    table(altered, "System")["instances"][0]["rows"][0][0] = "TAMPERED"
    path = tmp_path / "parent.json"
    path.write_text(json.dumps(altered), encoding="utf-8")
    monkeypatch.setattr(builder, "PARENT", path)
    with pytest.raises(ValueError, match="fingerprint"):
        builder.build()

    source = (CASE / "native-input.json").read_bytes()
    (tmp_path / "input.json").write_bytes(source)
    (tmp_path / "roundtrip-raw.json").write_bytes(source)
    (tmp_path / "model.sxi").write_bytes(b"test-model")
    (tmp_path / "import.log").write_text("Import completed!", encoding="utf-8")
    (tmp_path / "export.log").write_text("Export completed!", encoding="utf-8")
    assert checker.validate(tmp_path)["passed"]
    exported = read(tmp_path / "roundtrip-raw.json")
    table(exported, "SystemRepair")["instances"][0]["rows"][0][2] = 9.0
    (tmp_path / "roundtrip-raw.json").write_text(json.dumps(exported), encoding="utf-8")
    assert not checker.validate(tmp_path)["passed"]
