"""A09 v1.0.1 source delta and evidence-boundary checks; no native run."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest


CASE = Path(__file__).resolve().parents[2] / "cases/simlox-air-support/A09-hierarchical-operation-profile-v1.0.1"
spec = importlib.util.spec_from_file_location("simlox_a09_v101_build", CASE / "build.py")
assert spec is not None and spec.loader is not None
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_candidate_changes_exactly_one_native_cell_and_preserves_sources() -> None:
    contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8"))
    previous, candidate, raw = builder.build()
    assert builder.sha256(builder.PREVIOUS.read_bytes()) == contract["previous_input_sha256"]
    assert builder.sha256(builder.PARENT.read_bytes()) == contract["parent_input_sha256"]
    assert builder.sha256(builder.FLAT.read_bytes()) == contract["flat_control_sha256"]
    assert builder.sha256(raw) == contract["candidate_input_sha256"]
    assert (CASE / "native-nested.json").read_bytes() == raw

    # This comparison is independent of the builder's check_delta implementation.
    root, index = builder.root_period_cell(previous)
    assert root[index] == 24.0
    expected = copy.deepcopy(previous)
    revised_root, revised_index = builder.root_period_cell(expected)
    revised_root[revised_index] = 48.0
    assert candidate == expected
    assert [table["name"] for table in candidate["model"]["tables"]] == [
        table["name"] for table in previous["model"]["tables"]
    ]
    assert len(candidate["model"]["tables"]) == 31


@pytest.mark.parametrize("table_name,column,new_value", [
    ("OperationProfile", "IPER", 47.0),
    ("Control", "SIMPE", 49.0),
    ("MissionType", "DURN", 3.0),
])
def test_one_cell_gate_rejects_other_model_edits(table_name: str, column: str, new_value: float) -> None:
    previous, candidate, _ = builder.build()
    changed = copy.deepcopy(candidate)
    table = next(table for table in changed["model"]["tables"] if table["name"] == table_name)
    index = [entry["name"] for entry in table["columns"]].index(column)
    table["instances"][0]["rows"][0][index] = new_value
    with pytest.raises(ValueError, match="changes more than root IPER"):
        builder.check_delta(previous, changed)


def test_static_check_rejects_drifted_checked_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    drift = tmp_path / "nested.json"
    drift.write_bytes((CASE / "native-nested.json").read_bytes() + b"\n")
    monkeypatch.setattr(builder, "OUTPUT", drift)
    with pytest.raises(ValueError, match="checked candidate differs"):
        builder.validate()


def test_observed_failure_and_new_prediction_remain_separate() -> None:
    contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8"))
    flat = contract["v100_native_flat_control"]
    old = contract["v100_native_observation"]
    proposed = contract["v101_prediction_if_candidate_rule_holds"]
    assert flat["source_input_sha256"] == contract["flat_control_sha256"]
    assert flat["validation_passed"] is True
    assert flat["notification_hours"] == [7, 19, 31, 43]
    assert flat["launched_hours"] == [8, 20, 32, 44]
    assert old["source_input_sha256"] == contract["previous_input_sha256"]
    assert old["validation_passed"] is False
    assert old["notification_hours"] == [7, 19, 19, 31]
    assert old["launched_hours"] == [8, 20, 32]
    assert old["cancelled"][0]["hour_printed"] == 20.3333
    assert proposed["notification_hours"] == [7, 19, 31, 43]
    assert proposed["launch_hours"] == [8, 20, 32, 44]
    assert contract["interpretation"]["candidate_rule"].startswith("root instance separation may")
    assert contract["native_behavior_status"] == "not_run"
    assert contract["publication_state"] == "not_published"
    assert builder.validate()["scope"] == "local_static_candidate_only"
