from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import sim_engine_compiler.trace_query.facts as facts_module
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.review import export_review
from sim_engine_compiler.trace_query.facts import (
    FACTS_SCHEMA,
    _project_facts,
    _review_has_verified_authority,
    process_reference,
    project_facts,
)

FIXTURES = Path(__file__).parents[1] / "fixtures"


def _bundle(case: str = "b1") -> dict[str, dict]:
    root = FIXTURES / "identity_contract" / case
    return {
        name: json.loads((root / f"{name}.json").read_text())
        for name in ("business", "core", "plan", "lineage")
    }


def _review(case: str = "b1") -> dict:
    persisted = _bundle(case)
    return export_review(persisted["core"], bundle=persisted)


def _projector(case: str = "b1"):
    bundle = _bundle(case)
    return lambda raw_event: project_facts(raw_event, bundle=bundle)


def _events(name: str = "b1-reference-result.json") -> list[dict]:
    return json.loads((FIXTURES / "synthetic" / name).read_text())["trace"]


def _event(kind: str, name: str = "b1-reference-result.json") -> dict:
    return next(item for item in _events(name) if item["kind"] == kind)


def _gap_codes(facts: dict) -> set[str]:
    return {item["code"] for item in facts["evidence_gaps"]}


def test_recorded_job_event_preserves_fields_and_uses_only_versioned_process_meaning() -> None:
    raw = _event("operations_phase_created")
    before = copy.deepcopy(raw)

    facts = project_facts(raw)

    assert set(facts) == {
        "schema_version", "status", "recorded", "process", "design_links", "evidence_gaps",
    }
    assert facts["schema_version"] == FACTS_SCHEMA
    assert facts["status"] == "recorded"
    assert facts["recorded"] == raw
    assert facts["process"] == {
        "status": "versioned-event-contract",
        "reference": "job-0001",
        "basis": "reference-runtime-v1-kind-entity",
    }
    assert facts["design_links"] == {"status": "unavailable", "links": []}
    assert _gap_codes(facts) >= {
        "design_association_unverified", "trigger_not_recorded", "guard_evaluation_not_recorded",
    }
    assert raw == before
    assert not ({"cause", "causes", "trigger", "guard"} & set(facts))


def test_verified_review_links_only_exact_recorded_core_symbols_and_source_paths() -> None:
    raw = _event("operations_phase_created")

    facts = _projector()(raw)

    assert facts["design_links"]["status"] == "verified"
    links = facts["design_links"]["links"]
    by_field = {(item["recorded_field"], item["view_id"]) for item in links}
    assert ("details.activity_id", "core/activities/f35-daily-preflight") in by_field
    assert ("details.mission_id", "core/missions/sortie-a-d1-w1") in by_field
    assert ("details.tail_number", "core/aircraft/F35-01") in by_field
    assert ("source_path", "core/activities/f35-daily-preflight") in by_field
    assert not any(item["view_id"].startswith("core/missions/job-") for item in links)
    assert "design_association_unverified" not in _gap_codes(facts)


def test_entity_role_is_kind_scoped_and_never_cross_typed_by_string_coincidence() -> None:
    projector = _projector()
    returned = projector(_event("mission_returned"))
    launched = projector(_event("mission_launched"))

    returned_entity_links = [
        item for item in returned["design_links"]["links"]
        if item["recorded_field"] == "entity"
    ]
    launched_entity_links = [
        item for item in launched["design_links"]["links"]
        if item["recorded_field"] == "entity"
    ]
    assert {item["view_id"] for item in returned_entity_links} == {"core/aircraft/F35-01"}
    assert {item["view_id"] for item in launched_entity_links} == {
        "core/missions/sortie-a-d1-w1"
    }


def test_explicit_job_id_is_recorded_but_conflicting_process_fields_are_unknown() -> None:
    raw = _event("organization_transport_dispatched", "b3-upstream-transport-reference-result.json")
    assert process_reference(raw) == "job-0001"
    facts = project_facts(raw)
    assert facts["process"]["status"] == "recorded"
    assert facts["process"]["reference"] == "job-0001"
    assert facts["process"]["basis"] == "recorded.details.job_id"

    conflicting = copy.deepcopy(raw)
    conflicting["process_id"] = "job-other"
    assert process_reference(conflicting) is None
    conflict_facts = project_facts(conflicting)
    assert conflict_facts["process"] == {"status": "unknown", "reference": None, "basis": None}
    assert "process_reference_conflict" in _gap_codes(conflict_facts)

    entity_conflict = copy.deepcopy(raw)
    entity_conflict["details"]["job_id"] = "job-other"
    assert process_reference(entity_conflict) is None
    assert "process_reference_conflict" in _gap_codes(project_facts(entity_conflict))


def test_unknown_event_kind_is_capability_limited_and_does_not_infer_job_from_entity() -> None:
    raw = {
        "sequence": 99,
        "time": 4,
        "phase": "future_phase",
        "kind": "future_runtime_side_effect",
        "rule_id": "future.rule",
        "entity": "job-0001",
        "source_path": "support_activities.activities[0]",
        "details": {"opaque_future_field": {"kept": True}},
    }

    facts = _projector()(raw)

    assert facts["status"] == "capability_limited"
    assert facts["recorded"]["details"] == raw["details"]
    assert facts["process"] == {"status": "unknown", "reference": None, "basis": None}
    assert _gap_codes(facts) >= {
        "event_kind_capability_limited", "process_reference_not_recorded",
    }
    # Exact recorded source may still link; the unknown kind grants no entity-role link.
    assert all(item["recorded_field"] != "entity" for item in facts["design_links"]["links"])


def test_caller_supplied_review_cannot_authorize_design_links() -> None:
    raw = _event("mission_launched")
    persisted = _bundle()
    partial = export_review(persisted["core"], bundle={"core": persisted["core"]})
    forged = {
        "status": "partial",
        "association_status": "verified",
        "views": _review()["views"],
        "mappings": _review()["mappings"],
    }
    tampered = _review()
    tampered["views"]["entities"].pop()

    for review in (None, partial, forged, tampered):
        with pytest.raises(TypeError, match="unexpected keyword argument 'review'"):
            project_facts(raw, review=review)


def test_self_signed_review_envelope_cannot_authorize_design_links() -> None:
    forged = copy.deepcopy(_review())
    forged["views"]["entities"].append({
        "view_id": "core/aircraft/EVIL",
        "provenance": {"source_path": "forged.aircraft"},
    })
    forged["view_fingerprint"] = content_digest(forged["views"])
    unsigned = dict(forged)
    unsigned.pop("export_fingerprint")
    forged["export_fingerprint"] = content_digest(unsigned)
    assert _review_has_verified_authority(forged)
    assert not hasattr(facts_module, "_bundle_backed_review")
    raw = {
        "sequence": 1,
        "time": 0,
        "phase": "mission",
        "kind": "mission_returned",
        "entity": "EVIL",
        "source_path": "forged.aircraft",
        "details": {},
    }

    with pytest.raises(TypeError, match="unexpected keyword argument 'review'"):
        project_facts(raw, review=forged)
    with pytest.raises(TypeError, match="unexpected keyword argument 'review'"):
        _project_facts(raw, review=forged)

    disguised = project_facts(raw, bundle={"core": forged})
    assert disguised["design_links"] == {"status": "unavailable", "links": []}


def test_process_reference_does_not_promote_aircraft_mission_or_adjacent_events() -> None:
    assert process_reference(_event("mission_launched")) is None
    assert process_reference(_event("mission_returned")) is None
    assert process_reference(_event("component_failed", "b2-failure-repair-reference-result.json")) is None
    assert process_reference({"kind": "operations_step_started", "entity": "job-explicit"}) == "job-explicit"
    assert process_reference({"kind": "unknown", "entity": "job-explicit"}) is None


@pytest.mark.parametrize("value", [None, [], "event"])
def test_non_object_event_is_rejected(value) -> None:
    with pytest.raises(TypeError, match="raw_event"):
        project_facts(value)


def test_non_object_details_are_rejected_without_coercion() -> None:
    raw = copy.deepcopy(_event("simulation_stopped"))
    raw["details"] = ["not", "an", "object"]
    with pytest.raises(TypeError, match="details"):
        project_facts(raw)


def test_missing_details_remains_missing_and_is_not_materialized_as_recorded_empty_object() -> None:
    raw = copy.deepcopy(_event("simulation_stopped"))
    raw.pop("details")

    facts = project_facts(raw)

    assert facts["recorded"]["details"] is None
    assert "event_details_not_recorded" in _gap_codes(facts)
