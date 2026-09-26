"""Executable regressions for PR #20 horizon and trace completeness findings."""

from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest

from sim_engine_compiler.identity import (
    build_run_identity,
    project_event_references,
    resolve_event_reference,
)
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime


@pytest.fixture
def plan():
    path = Path(__file__).resolve().parents[1] / "fixtures/identity_contract/b1/plan.json"
    return ExecutionPlan.from_dict(json.loads(path.read_text()))


def bound_result(identity, sequences=(1, 2), time=10):
    return {
        "plan_fingerprint": identity["execution_contract"]["plan_fingerprint"],
        "seed": identity["request"]["seed"],
        "sample_index": identity["identity"]["sample_index"],
        "semantic_profile": identity["execution_contract"]["semantic_profile"],
        "time": time,
        "stop_reason": "natural_complete",
        "trace": [{"sequence": sequence, "time": time,
                   "phase": "mission_dispatch", "kind": "mission_started"}
                  for sequence in sequences],
    }


def reseal(report):
    report.pop("content_digest")
    report["content_digest"] = content_digest(report)
    return report


@pytest.mark.parametrize("horizon,time", [(0, 100), (9, 10)])
def test_result_after_requested_horizon_is_rejected(plan, horizon, time):
    identity = build_run_identity("repair", 0, 7, plan, horizon=horizon)
    report = project_event_references(identity, bound_result(identity, time=time))
    assert report["status"] == "invalid"
    assert report["diagnostics"][0]["code"] == "result_horizon_mismatch"


@pytest.mark.parametrize("time", [-1, True, "0", None, float("inf"), float("nan")])
def test_malformed_result_time_cannot_claim_complete(plan, time):
    identity = build_run_identity("repair", 0, 7, plan)
    result = bound_result(identity)
    result["time"] = time
    assert project_event_references(identity, result)["status"] == "invalid"


@pytest.mark.parametrize("time,code", [(-1, "event_horizon_mismatch"),
                                       (101, "event_horizon_mismatch"),
                                       (11, "event_result_time_mismatch")])
def test_event_outside_result_or_request_is_rejected_even_when_filtered(plan, time, code):
    identity = build_run_identity("repair", 0, 7, plan, horizon=100)
    result = bound_result(identity)
    result["trace"][1]["time"] = time
    report = project_event_references(identity, result, selected_sequences=[1])
    assert report["status"] == "invalid"
    assert report["diagnostics"][0]["code"] == code


@pytest.mark.parametrize("horizon,time,sequences", [(0, 0, ()), (0, 0, (1,)),
                                                   (100, 10, (1, 2)),
                                                   (10, 10, (1, 2))])
def test_boundary_and_early_times_do_not_infer_termination_reason(plan, horizon, time, sequences):
    identity = build_run_identity("repair", 0, 7, plan, horizon=horizon)
    report = project_event_references(identity, bound_result(identity, sequences, time))
    assert report["status"] == "valid"
    assert report["coverage"]["level"] == "complete"
    if report["events"]:
        assert resolve_event_reference(report, report["events"][0]["event_id"])["status"] == "valid"


def test_actual_reference_result_is_still_accepted_without_mutation(plan):
    identity = build_run_identity("repair", 0, 7, plan)
    result = SimpyReferenceRuntime(plan, seed=7).run()
    result.update(sample_index=0, semantic_profile=plan.semantic_profile)
    before = copy.deepcopy(result)
    report = project_event_references(identity, result)
    assert report["status"] == "valid"
    assert result == before


@pytest.mark.parametrize("natural", [True, False])
def test_actual_reference_early_stop_remains_legal(plan, natural):
    # A synthetic Plan variant exercises genuine runtime natural completion;
    # the other case reaches Plan duration before the larger request limit.
    plan = replace(plan, natural_completion_enabled=natural,
                   duration_minutes=1000 if natural else plan.duration_minutes)
    identity = build_run_identity("repair", 0, 7, plan, horizon=2000)
    result = SimpyReferenceRuntime(plan, seed=7).run()
    result.update(sample_index=0, semantic_profile=plan.semantic_profile)
    assert result["stop_reason"] == ("natural_complete" if natural else "duration")
    assert result["time"] < identity["request"]["horizon"]
    report = project_event_references(identity, result)
    assert report["status"] == "valid"
    assert report["coverage"]["level"] == "complete"


def test_missing_result_time_is_partial_and_cannot_be_rehashed_to_complete(plan):
    identity = build_run_identity("repair", 0, 7, plan)
    result = bound_result(identity)
    del result["time"]
    report = project_event_references(identity, result)
    assert report["status"] == "partial"
    assert report["coverage"]["reason"] == "result_time_missing"
    event_id = report["events"][0]["event_id"]
    assert resolve_event_reference(report, event_id)["status"] == "valid"
    report["status"] = "valid"
    report["coverage"].update(level="complete", reason="full_trace")
    assert resolve_event_reference(reseal(report), event_id)["status"] == "invalid"


@pytest.mark.parametrize("sequences,code", [((1, 8), "trace_sequence_incomplete"),
                                           ((8,), "trace_sequence_incomplete"),
                                           ((2, 1), "trace_sequence_reordered"),
                                           ((8, 1), "trace_sequence_reordered")])
def test_gaps_and_reordering_stay_partial_preserving_original_ids(plan, sequences, code):
    identity = build_run_identity("repair", 0, 7, plan)
    result = bound_result(identity, sequences)
    report = project_event_references(identity, result)
    assert report["status"] == "partial"
    assert report["coverage"]["reason"] == code
    assert code in {item["code"] for item in report["diagnostics"]}
    assert [item["recorded_sequence"] for item in report["events"]] == list(sequences)
    event_id = report["events"][0]["event_id"]
    filtered = project_event_references(identity, result, selected_sequences=[sequences[0]])
    assert filtered["coverage"]["level"] == "partial"
    assert filtered["events"][0]["event_id"] == event_id
    assert resolve_event_reference(filtered, event_id)["status"] == "valid"
    report["status"] = "valid"
    report["coverage"].update(level="complete", reason="full_trace")
    report["diagnostics"] = []
    assert resolve_event_reference(reseal(report), event_id)["status"] == "invalid"


@pytest.mark.parametrize("field,value", [("result_time", 5), ("request_horizon", 5)])
def test_resolver_rechecks_serialized_time_binding(plan, field, value):
    identity = build_run_identity("repair", 0, 7, plan)
    report = project_event_references(identity, bound_result(identity))
    report["evidence_binding"]["time_binding"][field] = value
    resolved = resolve_event_reference(reseal(report), report["events"][0]["event_id"])
    assert resolved["status"] == "invalid"


@pytest.mark.parametrize("observation", ["full", "summary"])
def test_horizon_validation_applies_without_full_trace(plan, observation):
    identity = build_run_identity("repair", 0, 7, plan, horizon=0, observation=observation)
    result = bound_result(identity, time=100)
    del result["trace"]
    assert project_event_references(identity, result)["status"] == "invalid"
