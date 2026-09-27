"""Recorded-only event facts for the bounded offline trace query contract.

The finite event vocabulary below is taken from the Python reference runtime's
``SimpyReferenceRuntime._emit`` call sites at the pinned task revision.  It is
not a general event ontology.  In particular, this module never turns temporal
adjacency into a trigger, cause, guard evaluation, or process relationship.

``review`` is an internal admission product: callers must obtain it through the
query package's validated raw-bundle path.  The integrity checks here prevent a
partial or edited envelope from authorizing links; they do not authenticate an
arbitrary third-party review document.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from sim_engine_compiler.identity.common import content_digest, json_value

FACTS_SCHEMA = "trace-event-facts/v1"

KNOWN_EVENT_KINDS = frozenset({
    "aircraft_failed",
    "component_failed",
    "equipment_shortage",
    "maintenance_method_selected",
    "mission_cancelled",
    "mission_failed_returned",
    "mission_launched",
    "mission_returned",
    "mission_returned_with_component_failure",
    "mission_success_point_failed",
    "mission_success_point_succeeded",
    "operations_phase_completed",
    "operations_phase_created",
    "operations_step_completed",
    "operations_step_started",
    "organization_spare_reservation_returned",
    "organization_supply_selected",
    "organization_transport_arrived",
    "organization_transport_dispatched",
    "personnel_delay",
    "postflight_completed",
    "preflight_completed",
    "preflight_created",
    "preventive_completed",
    "preventive_created",
    "repair_completed",
    "resources_released",
    "resources_reserved",
    "simulation_stopped",
    "spare_consumed",
    "spare_request",
    "spare_shortage",
    "transport_arrived",
})

# For these exact v1 runtime events, ``entity`` is the JobRuntimeState.job_id
# (or the reserved job ID immediately before creation for method selection).
_JOB_ENTITY_KINDS = frozenset({
    "equipment_shortage",
    "maintenance_method_selected",
    "operations_phase_completed",
    "operations_phase_created",
    "operations_step_completed",
    "operations_step_started",
    "organization_spare_reservation_returned",
    "organization_supply_selected",
    "organization_transport_arrived",
    "organization_transport_dispatched",
    "personnel_delay",
    "resources_released",
    "resources_reserved",
    "spare_consumed",
    "spare_request",
    "spare_shortage",
    "transport_arrived",
})

_AIRCRAFT_ENTITY_KINDS = frozenset({
    "aircraft_failed",
    "component_failed",
    "mission_failed_returned",
    "mission_returned",
    "mission_returned_with_component_failure",
    "postflight_completed",
    "preflight_completed",
    "preventive_completed",
    "preventive_created",
    "repair_completed",
})

_MISSION_ENTITY_KINDS = frozenset({
    "mission_cancelled",
    "mission_launched",
    "mission_success_point_failed",
    "mission_success_point_succeeded",
    "preflight_created",
})


def _nonempty(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _process_candidates(raw_event: Mapping[str, Any]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for name in ("process_id", "job_id"):
        value = _nonempty(raw_event.get(name))
        if value is not None:
            candidates.append((value, f"recorded.{name}"))
    details = raw_event.get("details")
    if isinstance(details, Mapping):
        for name in ("process_id", "job_id"):
            value = _nonempty(details.get(name))
            if value is not None:
                candidates.append((value, f"recorded.details.{name}"))
    return candidates


def process_reference(raw_event: Mapping[str, Any]) -> str | None:
    """Return one recorded/proven process reference, never an adjacency guess."""
    if not isinstance(raw_event, Mapping):
        return None
    explicit = _process_candidates(raw_event)
    values = {value for value, _basis in explicit}
    entity = _nonempty(raw_event.get("entity"))
    contract_reference = entity if raw_event.get("kind") in _JOB_ENTITY_KINDS else None
    if contract_reference is not None:
        values.add(contract_reference)
    if len(values) > 1:
        return None
    return next(iter(values)) if values else None


def _review_has_verified_authority(review: Any) -> bool:
    if not isinstance(review, Mapping):
        return False
    try:
        value = json_value(review)
        export_digest = value.get("export_fingerprint")
        unsigned = dict(value)
        unsigned.pop("export_fingerprint", None)
        if export_digest != content_digest(unsigned):
            return False
        if value.get("view_fingerprint") != content_digest(value.get("views")):
            return False
    except (RecursionError, TypeError, ValueError):
        return False
    bundle = value.get("bundle_identity")
    mappings = value.get("mappings")
    return bool(
        value.get("schema_version") == "model-review-data/v1"
        and value.get("exporter_version") == "review-exporter/v1"
        and value.get("status") == "partial"
        and value.get("association_status") == "verified"
        and isinstance(bundle, dict)
        and bundle.get("association_status") == "verified"
        and bundle.get("status") == "partial"
        and isinstance(mappings, dict)
        and mappings.get("core_to_plan")
        and bundle.get("mappings") == mappings
        and isinstance(value.get("views"), dict)
    )


def _view_index(review: Mapping[str, Any]) -> tuple[dict[str, tuple[str, dict[str, Any]]],
                                                   list[tuple[str, dict[str, Any]]]]:
    by_id: dict[str, tuple[str, dict[str, Any]]] = {}
    with_sources: list[tuple[str, dict[str, Any]]] = []
    for view_name in ("entities", "processes", "states", "rules", "resources"):
        values = review.get("views", {}).get(view_name, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("view_id"), str):
                continue
            by_id[item["view_id"]] = (view_name, item)
            provenance = item.get("provenance")
            if isinstance(provenance, dict) and _nonempty(provenance.get("source_path")):
                with_sources.append((view_name, item))
    return by_id, with_sources


def _design_links(
    event: Mapping[str, Any], bundle: Mapping[str, Any]
) -> list[dict[str, str]] | None:
    """Return links only after revalidating the supplied raw artifact bundle."""
    if not isinstance(bundle, Mapping) or bundle.get("core") is None:
        raise ValueError("raw bundle with Core is required for design associations")
    from sim_engine_compiler.review import export_review

    review = export_review(bundle["core"], bundle=bundle)
    if not _review_has_verified_authority(review):
        return None
    by_id, with_sources = _view_index(review)
    links: dict[tuple[str, str, str, str], dict[str, str]] = {}

    def add(view_id: str, basis: str, recorded_field: str) -> None:
        match = by_id.get(view_id)
        if match is None:
            return
        view_name, _item = match
        key = (view_name, view_id, basis, recorded_field)
        links[key] = {
            "view": view_name,
            "view_id": view_id,
            "basis": basis,
            "recorded_field": recorded_field,
        }

    source_path = _nonempty(event.get("source_path"))
    if source_path is not None:
        for view_name, item in with_sources:
            if item["provenance"]["source_path"] == source_path:
                key = (view_name, item["view_id"], "recorded-source-path-exact", "source_path")
                links[key] = {
                    "view": view_name,
                    "view_id": item["view_id"],
                    "basis": "recorded-source-path-exact",
                    "recorded_field": "source_path",
                }

    kind = event.get("kind")
    entity = _nonempty(event.get("entity"))
    if entity is not None and kind in _AIRCRAFT_ENTITY_KINDS:
        add(f"core/aircraft/{entity}", "versioned-event-entity-role", "entity")
    elif entity is not None and kind in _MISSION_ENTITY_KINDS:
        add(f"core/missions/{entity}", "versioned-event-entity-role", "entity")

    details = event.get("details", {})
    if isinstance(details, Mapping):
        scalar_links = {
            "activity_id": "activities",
            "mission_id": "missions",
            "component_id": "components",
            "tail_number": "aircraft",
        }
        for field, table in scalar_links.items():
            value = _nonempty(details.get(field))
            if value is not None:
                add(f"core/{table}/{value}", "recorded-stable-symbol-exact", f"details.{field}")
        aircraft = details.get("aircraft")
        if isinstance(aircraft, list):
            for index, value in enumerate(aircraft):
                identity = _nonempty(value)
                if identity is not None:
                    add(
                        f"core/aircraft/{identity}", "recorded-stable-symbol-exact",
                        f"details.aircraft[{index}]",
                    )
    return [links[key] for key in sorted(links)]


def _project_facts(
    raw_event: Mapping[str, Any],
    *,
    bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw_event, Mapping):
        raise TypeError("raw_event must be an object")
    event = json_value(raw_event)
    details = event.get("details")
    if details is not None and not isinstance(details, dict):
        raise TypeError("raw_event.details must be an object")
    recorded = {
        "sequence": copy.deepcopy(event.get("sequence")),
        "time": copy.deepcopy(event.get("time")),
        "phase": copy.deepcopy(event.get("phase")),
        "kind": copy.deepcopy(event.get("kind")),
        "rule_id": copy.deepcopy(event.get("rule_id")),
        "entity": copy.deepcopy(event.get("entity")),
        "source_path": copy.deepcopy(event.get("source_path")),
        "details": copy.deepcopy(details),
    }
    kind = event.get("kind")
    known = kind in KNOWN_EVENT_KINDS
    gaps: list[dict[str, str]] = []
    if not known:
        gaps.append({
            "code": "event_kind_capability_limited",
            "field": "kind",
            "reason": "event kind is outside the finite inspected runtime vocabulary",
        })

    explicit = _process_candidates(event)
    explicit_values = {value for value, _basis in explicit}
    entity_process = (
        _nonempty(event.get("entity")) if event.get("kind") in _JOB_ENTITY_KINDS else None
    )
    process_values = explicit_values | ({entity_process} if entity_process is not None else set())
    process = process_reference(event)
    if len(process_values) > 1:
        process_fact = {"status": "unknown", "reference": None, "basis": None}
        gaps.append({
            "code": "process_reference_conflict",
            "field": "process_id",
            "reason": "recorded process fields disagree",
        })
    elif explicit:
        process_fact = {
            "status": "recorded", "reference": process,
            "basis": min(basis for _value, basis in explicit),
        }
    elif process is not None:
        process_fact = {
            "status": "versioned-event-contract", "reference": process,
            "basis": "reference-runtime-v1-kind-entity",
        }
    else:
        process_fact = {"status": "unknown", "reference": None, "basis": None}
        gaps.append({
            "code": "process_reference_not_recorded",
            "field": "process",
            "reason": "event did not record a process and its kind does not define entity as a job",
        })

    if details is None:
        gaps.append({
            "code": "event_details_not_recorded",
            "field": "details",
            "reason": "event did not record a details object",
        })

    design_links = _design_links(event, bundle) if bundle is not None else None
    if design_links is not None:
        design_fact = {"status": "verified", "links": design_links}
        if not design_links:
            gaps.append({
                "code": "recorded_design_match_absent",
                "field": "design_links",
                "reason": "verified design was available but no recorded field matched a design node",
            })
    else:
        design_fact = {"status": "unavailable", "links": []}
        gaps.append({
            "code": "design_association_unverified",
            "field": "design_links",
            "reason": "a matching verified raw-bundle review association was not available",
        })

    gaps.extend((
        {
            "code": "trigger_not_recorded",
            "field": "trigger",
            "reason": "runtime event did not record a direct triggering event reference",
        },
        {
            "code": "guard_evaluation_not_recorded",
            "field": "guard",
            "reason": "runtime event did not record candidate or guard evaluation evidence",
        },
    ))
    return {
        "schema_version": FACTS_SCHEMA,
        "status": "recorded" if known else "capability_limited",
        "recorded": recorded,
        "process": process_fact,
        "design_links": design_fact,
        "evidence_gaps": sorted(gaps, key=lambda item: (item["code"], item["field"])),
    }


def project_facts(
    raw_event: Mapping[str, Any],
    *,
    bundle: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project one event; raw bundle authority is revalidated on every call."""
    return _project_facts(raw_event, bundle=bundle)
