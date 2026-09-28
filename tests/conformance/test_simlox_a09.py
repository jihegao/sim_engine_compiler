"""A09 local candidates and fail-closed static graph/diff checks."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest


CASE = Path(__file__).resolve().parents[2] / "cases/simlox-air-support/A09-hierarchical-operation-profile"
sys.path.insert(0, str(CASE))
spec = importlib.util.spec_from_file_location("simlox_a09_validate", CASE / "validate.py")
assert spec is not None and spec.loader is not None
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
builder = validator.build


def source(variant: str) -> dict:
    return json.loads((CASE / f"native-{variant}.json").read_text(encoding="utf-8"))


def mutate_row(document: dict, index: int, **updates: object) -> None:
    rows = builder.rows(document, "OperationProfile")
    rows[index].update(updates)
    builder.set_rows(document, "OperationProfile", rows)


def test_a09_inputs_rebuild_from_pinned_parent_and_diff_only_declared_tables() -> None:
    parent = json.loads(builder.PARENT.read_bytes())
    assert builder.sha256(builder.PARENT) == builder.PARENT_SHA256
    artifacts = builder.artifacts(validator.PARAMETERS)
    assert all((CASE / name).read_bytes() == raw for name, raw in artifacts.items())
    assert validator.validate()["passed"]
    flat, nested = source("flat"), source("nested")
    assert set(builder.changed_tables(parent, flat)) == builder.EXPECTED_PARENT_DIFF
    assert set(builder.changed_tables(parent, nested)) == builder.EXPECTED_PARENT_DIFF
    assert set(builder.changed_tables(flat, nested)) == {"OperationProfile"}
    assert builder.rows(flat, "Operations") == builder.rows(nested, "Operations") == builder.rows(parent, "Operations")
    assert builder.rows(flat, "MissionType") == builder.rows(nested, "MissionType") == builder.rows(parent, "MissionType")
    for variant in ("flat", "nested"):
        assert hashlib.sha256((CASE / f"native-{variant}.json").read_bytes()).hexdigest() == validator.CONTRACT["candidate_input_sha256"][variant]


def test_hypothesis_expands_four_distinct_waves_without_deduplicating_prid() -> None:
    flat, nested = source("flat"), source("nested")
    expected = [("BASIC-MISSION", hour) for hour in (8.0, 20.0, 32.0, 44.0)]
    assert validator.expand_hypothesis(flat) == expected
    assert validator.expand_hypothesis(nested) == expected
    assert [row["PRID"] for row in builder.rows(flat, "OperationProfile")] == ["BASIC-SCHEDULE"] * 4
    assert [row["PRID"] for row in builder.rows(nested, "OperationProfile")] == ["BASIC-SCHEDULE", "A09-DAILY-TWO-WAVE", "A09-DAILY-TWO-WAVE"]
    hand = validator.CONTRACT["hand_expected_if_native_expansion_matches_hypothesis"]
    assert hand["notification_hours"] == [start - 1 for _, start in expected]
    assert hand["end_hours"] == [start + 2 for _, start in expected]
    assert hand["flight_hours_integral"] == 2 * len(expected)
    assert hand["ready_hours_integral"] == 48 - 3 * len(expected)


@pytest.mark.parametrize("mutation,fragment", [
    (lambda doc: mutate_row(doc, 0, SPRID="MISSING-PROFILE"), "unresolved"),
    (lambda doc: mutate_row(doc, 1, SPRID="BASIC-SCHEDULE"), "cyclic"),
    (lambda doc: mutate_row(doc, 0, IPER=23.0), "expansion hypothesis differs"),
    (lambda doc: mutate_row(doc, 0, IQTY=0), "unsupported candidate profile row"),
    (lambda doc: mutate_row(doc, 0, ITYPE="RANDOM"), "unsupported candidate profile row"),
])
def test_static_check_rejects_broken_reference_or_wrong_expansion(mutation, fragment: str) -> None:
    parent = json.loads(builder.PARENT.read_bytes())
    changed = copy.deepcopy(source("nested"))
    mutation(changed)
    assert any(fragment in message for message in validator.check_candidate(parent, changed, "nested"))


def test_builder_rejects_parent_drift_and_unreviewed_parameters(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = copy.deepcopy(validator.PARAMETERS)
    p["repeat_period_hours"] = 23.0
    with pytest.raises(ValueError, match="reviewed, bounded candidate"):
        builder.build(p)
    drifted = tmp_path / "a02.json"
    drifted.write_bytes(builder.PARENT.read_bytes() + b"\n")
    monkeypatch.setattr(builder, "PARENT", drifted)
    with pytest.raises(ValueError, match="frozen A02 input changed"):
        builder.build(validator.PARAMETERS)


def test_contract_does_not_claim_native_or_complete_a09_coverage() -> None:
    contract = validator.CONTRACT
    assert contract["scope"] == "local_static_candidate_only"
    assert contract["native_behavior_status"] == contract["gui_status"] == "not_run"
    assert contract["publication_state"] == "not_published"
    assert contract["nested"]["expansion_semantics"].startswith("hypothesis_only")
    assert contract["coverage"]["A09.var02_IQTY_gt_1_IPER_0"] == "not_covered"
    assert contract["coverage"]["A09.var04_duplicate_rows_vs_IQTY"] == "not_covered"
    assert contract["coverage"]["A09.var05_illegal_child_random_regenerative"] == "not_covered"
