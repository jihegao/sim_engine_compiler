from __future__ import annotations

import copy
import json
from pathlib import Path

from sim_engine_compiler.identity import inspect_artifact
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR
from sim_engine_compiler.review.views import VIEW_SCHEMA, project_views

FIXTURES = Path(__file__).parents[1] / "fixtures" / "identity_contract"
VIEW_NAMES = {
    "entities", "relations", "processes", "states", "rules", "resources", "parameters",
}


def _load(case: str, layer: str) -> dict:
    return json.loads((FIXTURES / case / f"{layer}.json").read_text())


def _project(case: str, layer: str) -> tuple[dict, dict]:
    raw = _load(case, layer)
    return raw, project_views(raw, inspect_artifact(raw))


def _by_owner(values: list[dict], owner: str) -> dict:
    return next(value for value in values if value.get("owner_view_id") == owner)


def test_b1_business_view_uses_persisted_identity_and_exposes_review_semantics() -> None:
    raw, projection = _project("b1", "business")

    assert set(projection) == {"views", "diagnostics", "coverage"}
    assert set(projection["views"]) == VIEW_NAMES
    assert projection["diagnostics"] == []
    assert projection["coverage"]["schema_version"] == VIEW_SCHEMA
    assert projection["coverage"]["level"] == "partial"

    aircraft = next(
        item for item in projection["views"]["entities"]
        if item["view_id"] == "business/aircraft.assets/F35-01"
    )
    assert aircraft["qualified_identity"] == {
        "layer": "business", "kind": "aircraft.assets", "element_id": "F35-01",
    }
    assert aircraft["definition"]["initial_state"] == "available"
    assert _by_owner(projection["views"]["states"], aircraft["view_id"])["value"] == "available"

    process = _by_owner(
        projection["views"]["processes"],
        "business/support_activities.activities/f35-daily-preflight",
    )
    assert process["steps"][0]["step_id"] == "PRE-1"
    assert process["steps"][0]["definition"]["durationMinutes"] == 3
    node = _by_owner(
        projection["views"]["resources"], "business/support_network.nodes/flight-line",
    )
    assert node["capacities"] == {"personnel": 1, "equipment": 1}
    duration = next(
        item for item in projection["views"]["parameters"]
        if item["owner_view_id"]
        == "business/support_activities.activities/f35-daily-preflight"
        and item["logical_path"] == "jobs[activityCode=PRE-1].durationMinutes"
    )
    assert (duration["value"], duration["unit"], duration["unit_status"]) == (
        3, "minute", "known",
    )
    stop = next(rule for rule in projection["views"]["rules"] if rule["rule_kind"] == "stop-condition")
    assert stop["condition"] == {"type": "duration", "duration_minutes": 60}
    assert raw == _load("b1", "business")


def test_f35_business_view_preserves_real_predecessors_relations_resources_and_units() -> None:
    _, projection = _project("f35", "business")

    assert len(projection["views"]["entities"]) == 479
    service = _by_owner(
        projection["views"]["processes"],
        "business/support_activities.activities/f35-service-0103",
    )
    step_ids = {step["step_id"] for step in service["steps"]}
    assert {"F35-USE-015", "F35-USE-014", "F35-USE-002"} <= step_ids
    predecessor = next(
        relation for relation in projection["views"]["relations"]
        if relation["relation_kind"] == "predecessor"
        and relation["source"]["step_id"] == "F35-USE-014"
    )
    assert predecessor["target"]["step_id"] == "F35-USE-015"
    assert predecessor["resolution"] == "persisted-process-local"

    transition = next(
        rule for rule in projection["views"]["rules"]
        if rule["owner_view_id"] == "business/mission_profile.mission_phases/phase-prep"
    )
    assert transition["condition"] == "保障完成"
    assert transition["effect"] == {"state": "preparing"}
    requirement = _by_owner(
        projection["views"]["resources"],
        "business/support_activities.activities/f35-service-0103",
    )
    assert requirement["resource_kind"] == "work-step-requirement"
    assert set(requirement["requirements"]) == {"personnel", "equipment", "spares"}
    units = {parameter["unit"] for parameter in projection["views"]["parameters"]}
    assert {"minute", "hour", "day", "cycle", "count", "dimensionless"} <= units
    takeoff_interval = next(
        item for item in projection["views"]["parameters"]
        if item["owner_view_id"]
        == "business/support_activities.activities/preventive-f35-6"
        and item["logical_path"] == "takeoffLandingInterval"
    )
    assert (takeoff_interval["value"], takeoff_interval["unit"], takeoff_interval["unit_status"]) == (
        0, "cycle", "known",
    )


def test_core_view_keeps_symbolic_relations_and_coarse_operations_explicitly_partial() -> None:
    _, projection = _project("f35", "core")

    assert projection["coverage"]["level"] == "partial"
    assert {item["code"] for item in projection["diagnostics"]} == {"coarse_operation_mapping"}
    operations = [
        rule for rule in projection["views"]["rules"]
        if rule["rule_kind"] == "compatibility-phase-operation"
    ]
    assert len(operations) == 15
    dispatch = next(rule for rule in operations if rule["operation"] == "aircraft.resource_dispatch/v1")
    assert dispatch["view_id"] == "core/operation/aircraft.resource_dispatch/v1"
    assert dispatch["rule_kind"] == "compatibility-phase-operation"
    assert dispatch["coverage"] == "partial"
    assert dispatch["phase"] == "resource_dispatch"
    assert dispatch["condition"]["time"] == "canonical-phase-at-wakeup"
    assert "reservations" in dispatch["condition"]["reads"]
    assert "reservations" in dispatch["effect"]["writes"]
    assert all(item["status"] == "partial" for item in projection["coverage"]["operation_coverage"])
    contract = next(
        rule for rule in projection["views"]["rules"]
        if rule["rule_kind"] == "execution-contract"
    )
    assert contract["condition"]["semantic_profile"] == "legacy-minute-v1"
    assert contract["condition"]["work_policy"] == "stable-topological-serial"
    assert contract["condition"]["rng_profile"] == "legacy-sequential-v1"
    assert contract["effect"]["natural_completion_enabled"] is True

    component = next(
        item for item in projection["views"]["entities"]
        if item["view_id"] == "core/components/f35-part-2602030200000799"
    )
    assert component["qualified_identity"]["element_id"] == "components/f35-part-2602030200000799"
    aircraft_links = [
        relation for relation in projection["views"]["relations"]
        if relation["source"]["owner_view_id"] == component["view_id"]
        and relation["relation_kind"] == "aircraft_indexes"
    ]
    assert {link["target"]["qualified_id"] for link in aircraft_links} >= {
        "aircraft/F35-01", "aircraft/F35-09",
    }
    assert all(link["resolution"] == "validated-core-symbol" for link in aircraft_links)
    assert not any("runtime_process_instance" in item["view_id"] for item in projection["views"]["entities"])


def test_artifact_and_upstream_source_paths_remain_distinct_and_origins_unknown() -> None:
    _, business = _project("b1", "business")
    _, core = _project("b1", "core")

    business_aircraft = next(
        item for item in business["views"]["entities"] if item["view_id"].endswith("/F35-01")
    )
    assert business_aircraft["provenance"] == {
        "artifact_field_path": "payload.sections.aircraft.collections.assets[0].definition",
        "source_path": "aircraft.assets[0]",
        "value_origin": "unknown",
    }
    core_aircraft = next(
        item for item in core["views"]["entities"] if item["view_id"] == "core/aircraft/F35-01"
    )
    assert core_aircraft["provenance"]["artifact_field_path"].startswith("payload.tables.aircraft[")
    assert core_aircraft["provenance"]["source_path"] == "aircraft.assets[0]"
    assert {
        item["provenance"]["value_origin"]
        for projection in (business, core)
        for view in projection["views"].values()
        for item in view
        if "provenance" in item
    } == {"unknown"}


def test_entity_stable_ids_survive_persisted_collection_and_table_reordering() -> None:
    business_raw = _load("b1", "business")
    business_before = project_views(business_raw, inspect_artifact(business_raw))
    business_payload = copy.deepcopy(business_raw["payload"])
    business_payload["sections"]["aircraft"]["collections"]["assets"].reverse()
    reordered_business = BusinessIR.create(business_payload).to_dict()
    business_after = project_views(reordered_business, inspect_artifact(reordered_business))

    core_raw = _load("b1", "core")
    core_before = project_views(core_raw, inspect_artifact(core_raw))
    core_payload = copy.deepcopy(core_raw["payload"])
    core_payload["tables"]["aircraft"].reverse()
    reordered_core = CoreIR.create(core_payload).to_dict()
    core_after = project_views(reordered_core, inspect_artifact(reordered_core))

    assert {item["view_id"] for item in business_before["views"]["entities"]} == {
        item["view_id"] for item in business_after["views"]["entities"]
    }
    assert {item["view_id"] for item in core_before["views"]["entities"]} == {
        item["view_id"] for item in core_after["views"]["entities"]
    }
    assert all("[" not in item["view_id"] for item in core_after["views"]["entities"])

    f35 = _load("f35", "business")
    f35_before = project_views(f35, inspect_artifact(f35))
    f35_payload = copy.deepcopy(f35["payload"])
    f35_payload["sections"]["equipment_tree"]["collections"]["components"].reverse()
    reordered_f35 = BusinessIR.create(f35_payload).to_dict()
    f35_after = project_views(reordered_f35, inspect_artifact(reordered_f35))
    assert {item["view_id"] for item in f35_before["views"]["relations"]} == {
        item["view_id"] for item in f35_after["views"]["relations"]
    }


def test_persisted_rule_edit_changes_review_content_without_inventing_core_mapping() -> None:
    raw = _load("f35", "business")
    before = project_views(raw, inspect_artifact(raw))
    payload = copy.deepcopy(raw["payload"])
    phase = payload["sections"]["mission_profile"]["collections"]["mission_phases"][1]
    phase["definition"]["transitionCondition"] = "人工复核后保障完成"
    edited = BusinessIR.create(payload).to_dict()

    after = project_views(edited, inspect_artifact(edited))

    before_rule = next(
        rule for rule in before["views"]["rules"]
        if rule["owner_view_id"] == "business/mission_profile.mission_phases/phase-prep"
    )
    after_rule = next(
        rule for rule in after["views"]["rules"]
        if rule["owner_view_id"] == "business/mission_profile.mission_phases/phase-prep"
    )
    assert before_rule["view_id"] == after_rule["view_id"]
    assert before_rule["condition"] == "保障完成"
    assert after_rule["condition"] == "人工复核后保障完成"
    assert "core" not in after["coverage"]
    assert any("no Business-to-Core" in item for item in after["coverage"]["limitations"])


def test_projection_rejects_unvalidated_or_mismatched_identity_reports_fail_closed() -> None:
    business = _load("b1", "business")
    report = inspect_artifact(business)
    mismatched = copy.deepcopy(business)
    mismatched["payload"]["sections"]["project_identity"]["properties"]["project_version"] = "2"

    mismatch = project_views(mismatched, report)
    invalid = project_views(business, {**report, "status": "invalid"})

    assert all(not values for values in mismatch["views"].values())
    assert mismatch["diagnostics"][0]["code"] == "review_artifact_identity_mismatch"
    assert all(not values for values in invalid["views"].values())
    assert invalid["diagnostics"][0]["code"] == "review_artifact_not_validated"


def test_behavioral_strings_booleans_and_strict_unit_metadata_are_preserved() -> None:
    _, business = _project("b1", "business")
    _, core = _project("b1", "core")

    business_parameters = {
        (item["owner_view_id"], item["logical_path"]): item
        for item in business["views"]["parameters"]
    }
    assert business_parameters[("business/section/stop_policy", "mode")]["value"] == "or"
    assert business_parameters[("business/section/stop_policy", "defaulted")]["value"] is False
    assert business_parameters[("business/section/$root", "seed")]["unit_status"] == "unknown"
    assert business_parameters[("business/section/$root", "seed")]["unit"] is None

    core_parameters = {
        (item["owner_view_id"], item["logical_path"]): item
        for item in core["views"]["parameters"]
    }
    assert core_parameters[("core/contract", "semantic_profile")]["value"] == "legacy-minute-v1"
    assert core_parameters[("core/contract", "natural_completion_enabled")]["value"] is False
    duration = core_parameters[("core/contract", "duration_minutes")]
    assert (duration["unit"], duration["unit_status"], duration["unit_source"]) == (
        "minute", "known", "aircraft-design-review-units/v1",
    )
    priority = next(
        item for item in core["views"]["parameters"]
        if item["logical_path"] == "priority"
    )
    assert priority["unit"] is None
    assert priority["unit_status"] == "unknown"


def test_missing_business_predecessor_is_not_claimed_as_resolved() -> None:
    raw = _load("b1", "business")
    payload = copy.deepcopy(raw["payload"])
    activity = payload["sections"]["support_activities"]["collections"]["activities"][0]
    activity["definition"]["jobs"][0]["predecessors"] = ["DOES-NOT-EXIST"]
    edited = BusinessIR.create(payload).to_dict()

    projection = project_views(edited, inspect_artifact(edited))

    relation = next(
        item for item in projection["views"]["relations"]
        if item["relation_kind"] == "predecessor"
        and item["target"]["step_id"] == "DOES-NOT-EXIST"
    )
    assert relation["resolution"] == "unresolved"
    assert "review_process_predecessor_unresolved" in {
        item["code"] for item in projection["diagnostics"]
    }


def test_duplicate_business_step_identity_fails_closed_without_duplicate_view_ids() -> None:
    raw = _load("b1", "business")
    payload = copy.deepcopy(raw["payload"])
    activity = payload["sections"]["support_activities"]["collections"]["activities"][0]
    activity["definition"]["jobs"].append(copy.deepcopy(activity["definition"]["jobs"][0]))
    edited = BusinessIR.create(payload).to_dict()

    projection = project_views(edited, inspect_artifact(edited))

    assert "review_process_step_identity_ambiguous" in {
        item["code"] for item in projection["diagnostics"]
    }
    assert any(item["severity"] == "error" for item in projection["diagnostics"])
    assert not any(
        item["owner_view_id"] == "business/support_activities.activities/f35-daily-preflight"
        for item in projection["views"]["processes"]
    )
    for values in projection["views"].values():
        view_ids = [item["view_id"] for item in values]
        assert len(view_ids) == len(set(view_ids))
    # The generic identity guard also catches repeated logical parameter paths
    # instead of falling back to an array position as a pseudo-identity.
    assert "review_duplicate_view_identity" in {
        item["code"] for item in projection["diagnostics"]
    }
