"""Independent adversarial controls for the public identity boundary.

These tests intentionally use persisted artifacts and caller-controlled JSON.
They do not reach through to a hidden canonical object or mutate the runtime.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sim_engine_compiler.compiler.layout import compile_core, lineage
from sim_engine_compiler.identity import (
    build_run_identity,
    inspect_artifact,
    inspect_bundle,
    inspect_run_identity,
    project_event_references,
    resolve_event_reference,
)
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR, digest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/identity_contract"


def load(case: str, layer: str):
    return json.loads((FIXTURES / case / f"{layer}.json").read_text())


def codes(report):
    return {item["code"] for item in report["diagnostics"]}


def trace_result(identity, *events):
    return {
        "plan_fingerprint": identity["execution_contract"]["plan_fingerprint"],
        "seed": identity["request"]["seed"],
        "sample_index": identity["identity"]["sample_index"],
        "semantic_profile": identity["execution_contract"]["semantic_profile"],
        "trace": list(events),
    }


def event(sequence: int):
    return {
        "sequence": sequence,
        "time": sequence,
        "phase": "mission_dispatch",
        "kind": "mission_started",
        "rule_id": "mission-dispatch/v1",
        "entity": "sortie-a-d1-w1",
        "source_path": "mission_profile.composite_tasks[0].taskItems[0]",
    }


def test_rehashed_edited_core_cannot_be_paired_with_stale_business():
    business_raw = load("b1", "business")
    business = BusinessIR.from_dict(business_raw)
    payload = copy.deepcopy(load("b1", "core")["payload"])
    payload["contract"]["duration_minutes"] += 1
    edited_core = CoreIR.create(payload)
    edited_plan = compile_core(edited_core)

    # Every envelope and lineage fingerprint is internally fresh.  What is
    # stale is the semantic Business -> Core relationship.
    report = inspect_bundle(
        business=business_raw,
        core=edited_core.to_dict(),
        plan=json.loads(json.dumps(edited_plan.to_dict())),
        lineage=lineage(business, edited_core, edited_plan),
    )

    assert report["status"] == "invalid"
    assert "business_core_revision_mismatch" in codes(report)
    assert report["association_status"] != "verified"


def test_independent_core_is_partial_and_does_not_guess_business_mapping():
    report = inspect_bundle(core=load("b1", "core"))

    assert report["status"] == "partial"
    assert report["association_status"] == "partial"
    assert report["mappings"]["business_to_core"] == []
    assert "business_missing" in codes(report)


def test_unknown_operation_with_recomputed_checksum_is_rejected():
    raw = load("b1", "core")
    raw["payload"]["operations"][0]["operation"] = "invented.side_effect/v9"
    raw["fingerprint"] = digest({"version": raw["version"], "payload": raw["payload"]})

    report = inspect_artifact(raw)

    assert report["status"] == "unsupported"
    assert "unsupported_operation" in codes(report)


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (lambda plan: plan.__setitem__("duration_minutes", True), "artifact_validation_failed"),
        (lambda plan: plan.__setitem__("domain", "abm-tick"), "unsupported_plan_domain"),
        (lambda plan: plan.__setitem__("semantic_profile", "unknown-v9"), "unsupported_semantic_profile"),
    ],
)
def test_plan_only_boundary_rejects_bad_type_or_unsupported_contract(mutate, expected_code):
    raw = load("b1", "plan")
    mutate(raw)

    report = inspect_artifact(raw)

    assert report["status"] in ("invalid", "unsupported")
    assert expected_code in codes(report)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["aircraft"][0].__setitem__("index", True),
        lambda plan: plan["activities"][0]["steps"][0].__setitem__(
            "duration_minutes", True
        ),
        lambda plan: plan["activities"][0].__setitem__("resource_node_index", 999),
        lambda plan: plan["aircraft"][1].__setitem__(
            "tail_number", plan["aircraft"][0]["tail_number"]
        ),
    ],
)
def test_plan_only_boundary_rejects_invalid_nested_layout(mutate):
    raw = load("b1", "plan")
    mutate(raw)

    report = inspect_artifact(raw)

    assert report["status"] == "invalid"
    assert "artifact_validation_failed" in codes(report)


def test_standalone_lineage_rejects_nonhex_hash_and_malformed_symbols():
    raw = load("b1", "lineage")
    raw["core_fingerprint"] = "z" * 64
    raw["symbols"] = {"aircraft": "not-a-symbol-list"}

    report = inspect_artifact(raw)

    assert report["status"] == "invalid"
    assert {"invalid_lineage_fingerprint", "invalid_lineage_symbols"} <= codes(report)


def test_cyclic_python_mapping_is_a_structured_error():
    hostile = {}
    hostile["cycle"] = hostile

    report = inspect_artifact(hostile)

    assert report["status"] == "invalid"
    assert "invalid_json_value" in codes(report)


@pytest.mark.parametrize("bad_value", [{"tuple": (1, 2)}, {"value": object()}])
def test_bundle_non_json_value_is_a_structured_error(bad_value):
    report = inspect_bundle(business=bad_value)

    assert report["status"] == "invalid"
    assert report["diagnostics"]
    assert "invalid_json_value" in codes(report["layers"]["business"])


def test_bundle_rejects_valid_artifact_in_the_wrong_layer_slot():
    report = inspect_bundle(business=load("b1", "plan"))

    assert report["status"] == "invalid"
    assert "bundle_layer_mismatch" in codes(report)


@pytest.mark.parametrize(
    "path",
    [
        Path("tests/fixtures/abm/fire-plan.json"),
        Path("experiments/ir_validation/results/cases/M04_domain_production/business.json"),
    ],
)
def test_other_real_domain_artifacts_are_explicitly_isolated(path):
    raw = json.loads((Path(__file__).resolve().parents[2] / path).read_text())

    report = inspect_artifact(raw)

    assert report["status"] == "unsupported"
    assert codes(report) & {"unsupported_artifact_domain", "unsupported_artifact_schema"}


def test_same_seed_has_distinct_sample_identity():
    plan = load("b1", "plan")
    first = build_run_identity("batch-7", 0, 17, plan)
    second = build_run_identity("batch-7", 1, 17, plan)

    assert first["status"] == second["status"] == "valid"
    assert first["request"]["seed"] == second["request"]["seed"]
    assert first["identity"]["sample_id"] != second["identity"]["sample_id"]


@pytest.mark.parametrize(
    "kwargs,code",
    [
        ({"sample_index": True}, "invalid_sample_index"),
        ({"seed": False}, "invalid_seed"),
        ({"sample_index": -1}, "invalid_sample_index"),
        ({"parameters": {"rate": float("nan")}}, "invalid_parameters"),
    ],
)
def test_run_identity_rejects_bool_integer_aliases_and_nonfinite_values(kwargs, code):
    arguments = {"run_id": "run-a", "sample_index": 0, "seed": 4,
                 "plan": load("b1", "plan")}
    arguments.update(kwargs)

    report = build_run_identity(**arguments)

    assert report["status"] == "invalid"
    assert code in codes(report)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["aircraft"][0].__setitem__("index", True),
        lambda plan: plan["activities"][0]["steps"][0].__setitem__(
            "duration_minutes", True
        ),
        lambda plan: plan["activities"][0].__setitem__("resource_node_index", 999),
        lambda plan: plan["aircraft"][1].__setitem__(
            "tail_number", plan["aircraft"][0]["tail_number"]
        ),
    ],
)
def test_run_identity_rejects_invalid_nested_plan(mutate):
    plan = load("b1", "plan")
    mutate(plan)

    report = build_run_identity("run-a", 0, 4, plan)

    assert report["status"] == "invalid"
    assert report["diagnostics"]


def test_rehashed_run_identity_cannot_add_unrecognized_evidence_fields():
    report = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    forged = copy.deepcopy(report)
    forged["identity"]["executed"] = True
    forged["request"]["evidence"] = "complete"
    forged.pop("content_digest")
    forged["content_digest"] = content_digest(forged)

    inspected = inspect_run_identity(forged)

    assert inspected["status"] == "invalid"
    assert inspected["diagnostics"]


def test_complete_bundle_run_identity_survives_reinspection_without_status_drift():
    bundle = {layer: load("b1", layer)
              for layer in ("business", "core", "plan", "lineage")}
    built = build_run_identity("run-a", 0, 4, bundle["plan"], bundle=bundle)

    inspected = inspect_run_identity(built)

    assert built["status"] == inspected["status"]
    assert built["identity"] == inspected["identity"]
    assert built["bundle_binding"] == inspected["bundle_binding"]


def test_rehashed_caller_claim_cannot_upgrade_execution_evidence():
    report = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    forged = copy.deepcopy(report)
    forged["execution_evidence"] = {
        "status": "complete",
        "proves_runtime_consumed_plan": True,
    }
    forged["status"] = "valid"
    forged.pop("content_digest")
    forged["content_digest"] = content_digest(forged)

    inspected = inspect_run_identity(forged)

    assert inspected["status"] != "valid" or not inspected["execution_evidence"][
        "proves_runtime_consumed_plan"
    ]
    assert "invalid_run_identity_evidence" in codes(inspected)


def test_trace_without_binding_fields_cannot_claim_complete_evidence():
    identity = build_run_identity("run-a", 0, 4, load("b1", "plan"))

    projection = project_event_references(identity, {"trace": [event(1)]})

    assert projection["status"] == "partial"
    assert projection["coverage"]["level"] != "complete"
    assert not projection["evidence_binding"]["proves_runtime_consumed_plan"]
    assert "evidence_insufficient" in codes(projection)


def test_event_identity_survives_filter_and_omitted_reference_is_explicit():
    identity = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    result = trace_result(identity, event(1), event(8))
    complete = project_event_references(identity, result)
    filtered = project_event_references(identity, result, selected_sequences=[8])

    assert complete["events"][1]["event_id"] == filtered["events"][0]["event_id"]
    missing = resolve_event_reference(filtered, complete["events"][0]["event_id"])
    assert missing["status"] == "partial"
    assert missing["reason"] == "event_filtered"
    assert "evidence_insufficient" in codes(missing)


def test_cross_sample_event_reference_is_not_resolved():
    plan = load("b1", "plan")
    identity_a = build_run_identity("run-a", 0, 4, plan)
    identity_b = build_run_identity("run-a", 1, 4, plan)
    projection_a = project_event_references(identity_a, trace_result(identity_a, event(1)))
    projection_b = project_event_references(identity_b, trace_result(identity_b, event(1)))

    resolved = resolve_event_reference(projection_a, projection_b["events"][0]["event_id"])

    assert resolved["status"] == "invalid"
    assert "cross_sample_event_reference" in codes(resolved)


def test_rehashed_projection_cannot_inject_foreign_event_identity():
    identity = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    projection = project_event_references(identity, trace_result(identity, event(1)))
    forged = copy.deepcopy(projection)
    forged["events"][0]["event_id"] = "event:" + "a" * 64
    forged.pop("content_digest")
    forged["content_digest"] = content_digest(forged)

    resolved = resolve_event_reference(forged, "event:" + "a" * 64)

    assert resolved["status"] == "invalid"
    assert "event_identity_mismatch" in codes(resolved)


def test_rehashed_projection_cannot_invent_trigger_or_mapping_evidence():
    identity = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    projection = project_event_references(identity, trace_result(identity, event(1)))
    forged = copy.deepcopy(projection)
    forged["events"][0]["trigger_relation"] = {
        "status": "known",
        "event_ids": [forged["events"][0]["event_id"]],
        "reason": "caller_invented",
    }
    forged["events"][0]["reference_scope"]["core_plan_element"] = "complete"
    forged.pop("content_digest")
    forged["content_digest"] = content_digest(forged)

    resolved = resolve_event_reference(forged, forged["events"][0]["event_id"])

    assert resolved["status"] == "invalid"
    assert resolved["diagnostics"]


def test_rehashed_projection_cannot_upgrade_partial_coverage_to_complete():
    identity = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    projection = project_event_references(identity, {"trace": [event(1)]})
    assert projection["coverage"]["level"] == "partial"
    forged = copy.deepcopy(projection)
    forged["coverage"]["level"] = "complete"
    forged["coverage"]["reason"] = "full_trace"
    forged["authenticated"] = True
    forged.pop("content_digest")
    forged["content_digest"] = content_digest(forged)

    resolved = resolve_event_reference(forged, forged["events"][0]["event_id"])

    assert resolved["status"] == "invalid"
    assert resolved["diagnostics"]


@pytest.mark.parametrize("observation", ["summary", "missing-trace"])
def test_uncollected_projection_resolves_as_evidence_insufficient(observation):
    plan = load("b1", "plan")
    full_identity = build_run_identity("run-a", 0, 4, plan)
    full = project_event_references(
        full_identity, trace_result(full_identity, event(1))
    )
    if observation == "summary":
        identity = build_run_identity("run-a", 0, 4, plan, observation="summary")
    else:
        identity = full_identity
    projection = project_event_references(identity, {})

    resolved = resolve_event_reference(projection, full["events"][0]["event_id"])

    assert resolved["status"] == "partial"
    assert "evidence_insufficient" in codes(resolved)


@pytest.mark.parametrize(
    ("field", "value"),
    [("time", True), ("phase", {"bad": "shape"}), ("kind", ["bad"])],
)
def test_unparseable_trace_field_types_are_rejected(field, value):
    identity = build_run_identity("run-a", 0, 4, load("b1", "plan"))
    bad_event = event(1)
    bad_event[field] = value

    projection = project_event_references(identity, trace_result(identity, bad_event))

    assert projection["status"] == "invalid"
    assert "unparseable_trace" in codes(projection)


def test_summary_missing_trace_and_truncation_are_evidence_insufficient():
    plan = load("b1", "plan")
    summary = build_run_identity("run-a", 0, 4, plan, observation="summary")
    full = build_run_identity("run-a", 1, 4, plan)

    summary_projection = project_event_references(summary, {})
    missing_projection = project_event_references(full, {})
    truncated_projection = project_event_references(
        full, trace_result(full, event(1)), truncated=True
    )

    assert summary_projection["coverage"]["reason"] == "summary_observation"
    assert missing_projection["coverage"]["reason"] == "trace_not_captured"
    assert truncated_projection["coverage"]["reason"] == "trace_truncated"
    for report in (summary_projection, missing_projection, truncated_projection):
        assert report["status"] == "partial"
        assert "evidence_insufficient" in codes(report)
