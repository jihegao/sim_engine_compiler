"""Independent adversarial controls for the offline review-data boundary.

The tests use only persisted artifacts.  In particular, they never recover a
canonical input behind a Business/Core envelope and never accept a Plan path
unless the complete persisted bundle and lineage validate together.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sim_engine_compiler.compiler.layout import compile_core, lineage
from sim_engine_compiler.identity import inspect_artifact
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR, digest
from sim_engine_compiler.review import export_review

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "identity_contract"
VIEW_NAMES = {
    "entities",
    "relations",
    "processes",
    "states",
    "rules",
    "resources",
    "parameters",
}
DIAGNOSTIC_FIELDS = {
    "code",
    "severity",
    "stage",
    "path",
    "element_id",
    "message",
    "reason",
}


def load(case: str, layer: str):
    return json.loads((FIXTURES / case / f"{layer}.json").read_text())


def bundle(case: str) -> dict:
    return {
        layer: load(case, layer)
        for layer in ("business", "core", "plan", "lineage")
    }


def codes(report: dict) -> set[str]:
    return {item["code"] for item in report["diagnostics"]}


def assert_diagnostics_are_machine_locatable(report: dict) -> None:
    for item in report["diagnostics"]:
        assert DIAGNOSTIC_FIELDS <= set(item)
        assert item["code"]
        assert item["severity"] in {"warning", "error"}
        assert item["stage"]
        assert item["message"]
        assert item["reason"]


def assert_no_admitted_views(report: dict) -> None:
    # Fail-closed reports expose no view namespace.  This differs deliberately
    # from an accepted default projection, which contains all seven lists.
    assert report["views"] == {}


@pytest.mark.parametrize("case", ["b1", "f35"])
def test_persisted_business_export_is_deterministic_and_bound_to_public_identity(case):
    raw = load(case, "business")

    first = export_review(raw)
    second = export_review(json.loads(json.dumps(raw, sort_keys=True)))

    assert first == second
    assert first["schema_version"] == "model-review-data/v1"
    assert first["exporter_version"] == "review-exporter/v1"
    assert first["status"] == "partial"
    assert set(first["views"]) == VIEW_NAMES
    assert first["input_identity"] == inspect_artifact(raw)
    assert first["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert_diagnostics_are_machine_locatable(first)


@pytest.mark.parametrize("case", ["b1", "f35"])
def test_complete_verified_bundle_is_the_only_source_of_plan_locations(case):
    persisted = bundle(case)

    report = export_review(persisted["business"], bundle=persisted)

    assert report["status"] == "partial"
    assert report["mappings"]["business_to_core"]
    assert report["mappings"]["core_to_plan"]
    for row in report["mappings"]["business_to_core"]:
        assert isinstance(row["business_element_id"], str)
        assert row["business_element_id"]
        for target in row["core_elements"]:
            assert isinstance(target["element_id"], str)
            assert isinstance(target["qualified_id"], str)
    for row in report["mappings"]["core_to_plan"]:
        assert isinstance(row["core_element"]["element_id"], str)
        assert row["basis"] == "verified-compiler-lineage/v2"
        assert isinstance(row["plan_path"], str)


def test_missing_lineage_never_emits_core_to_plan_mapping():
    persisted = bundle("b1")
    persisted.pop("lineage")

    report = export_review(persisted["core"], bundle=persisted)

    assert report["status"] == "partial"
    assert report["mappings"]["core_to_plan"] == []
    assert "lineage_missing" in codes(report)
    assert_diagnostics_are_machine_locatable(report)


def test_forged_lineage_invalidates_the_bundle_and_all_association_claims():
    persisted = bundle("b1")
    persisted["lineage"]["plan_fingerprint"] = "0" * 64

    report = export_review(persisted["business"], bundle=persisted)

    assert report["status"] == "invalid"
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert_no_admitted_views(report)
    assert "lineage_fingerprint_mismatch" in codes(report)
    assert_diagnostics_are_machine_locatable(report)


def test_primary_artifact_must_be_the_same_revision_as_its_bundle_slot():
    report = export_review(load("f35", "business"), bundle=bundle("b1"))

    assert report["status"] == "invalid"
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert_no_admitted_views(report)
    assert "review_primary_bundle_mismatch" in codes(report)
    assert_diagnostics_are_machine_locatable(report)


def test_rehashed_core_revision_cannot_be_associated_with_the_old_business():
    persisted = bundle("b1")
    business = BusinessIR.from_dict(persisted["business"])
    payload = copy.deepcopy(persisted["core"]["payload"])
    payload["contract"]["duration_minutes"] += 1
    edited_core = CoreIR.create(payload)
    edited_plan = compile_core(edited_core)
    persisted.update(
        core=edited_core.to_dict(),
        plan=json.loads(json.dumps(edited_plan.to_dict())),
        lineage=lineage(business, edited_core, edited_plan),
    )

    report = export_review(persisted["core"], bundle=persisted)

    assert report["status"] == "invalid"
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert_no_admitted_views(report)
    assert "business_core_revision_mismatch" in codes(report)
    assert_diagnostics_are_machine_locatable(report)


def test_standalone_edited_core_is_reviewable_but_does_not_guess_business():
    payload = copy.deepcopy(load("b1", "core")["payload"])
    payload["contract"]["duration_minutes"] += 1
    edited = CoreIR.create(payload).to_dict()

    report = export_review(edited)

    assert report["status"] == "partial"
    assert report["input_identity"] == inspect_artifact(edited)
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert report["views"]["entities"]
    assert_diagnostics_are_machine_locatable(report)


def test_unknown_operation_is_unsupported_even_with_a_fresh_checksum():
    raw = load("b1", "core")
    raw["payload"]["operations"][0]["operation"] = "invented.side-effect/v9"
    raw["fingerprint"] = digest({"version": raw["version"], "payload": raw["payload"]})

    report = export_review(raw)

    assert report["status"] == "unsupported"
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert "unsupported_operation" in codes(report)
    assert_no_admitted_views(report)
    assert_diagnostics_are_machine_locatable(report)


def test_unknown_profile_is_unsupported_even_with_a_fresh_checksum():
    raw = load("b1", "business")
    raw["payload"]["semantic_profile"] = "future-time-v9"
    raw["fingerprint"] = digest({"version": raw["version"], "payload": raw["payload"]})

    report = export_review(raw)

    assert report["status"] == "unsupported"
    assert "unsupported_semantic_profile" in codes(report)
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert_no_admitted_views(report)
    assert_diagnostics_are_machine_locatable(report)


def test_experimental_production_schema_is_isolated_from_aircraft_review_contract():
    raw = json.loads(
        (ROOT / "experiments" / "ir_validation" / "results" / "cases"
         / "M04_domain_production" / "business.json").read_text()
    )

    report = export_review(raw)

    assert report["status"] == "unsupported"
    assert codes(report) & {"unsupported_artifact_domain", "unsupported_artifact_schema"}
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert_no_admitted_views(report)
    assert_diagnostics_are_machine_locatable(report)


def test_missing_business_source_path_remains_unknown_instead_of_being_invented():
    raw = load("b1", "business")
    first_asset = raw["payload"]["sections"]["aircraft"]["collections"]["assets"][0]
    first_asset["source_path"] = ""
    raw["fingerprint"] = digest({"version": raw["version"], "payload": raw["payload"]})

    report = export_review(raw)
    entity = next(
        row
        for row in report["views"]["entities"]
        if row["qualified_identity"]["element_id"] == first_asset["business_id"]
    )

    assert report["status"] == "partial"
    assert not entity["provenance"]["source_path"]
    assert entity["provenance"]["value_origin"] == "unknown"
    # Artifact navigation is allowed, but it must not be represented as an
    # upstream source path when that provenance was absent.
    assert entity["provenance"]["artifact_field_path"]
    assert entity["provenance"]["artifact_field_path"] != entity["provenance"]["source_path"]
    assert_diagnostics_are_machine_locatable(report)


def test_reordering_persisted_business_rows_preserves_stable_view_identities():
    raw = load("b1", "business")
    reordered = copy.deepcopy(raw)
    reordered["payload"]["sections"]["aircraft"]["collections"]["assets"].reverse()
    reordered["fingerprint"] = digest(
        {"version": reordered["version"], "payload": reordered["payload"]}
    )

    original_report = export_review(raw)
    reordered_report = export_review(reordered)

    for view_name in VIEW_NAMES:
        original_ids = {row["view_id"] for row in original_report["views"][view_name]}
        reordered_ids = {row["view_id"] for row in reordered_report["views"][view_name]}
        assert reordered_ids == original_ids
    assert reordered_report["input_identity"]["identity"]["artifact_fingerprint"] != (
        original_report["input_identity"]["identity"]["artifact_fingerprint"]
    )


def test_business_rule_edit_changes_revision_and_review_fingerprint():
    raw = load("b1", "business")
    edited = copy.deepcopy(raw)
    mission = edited["payload"]["sections"]["mission_profile"]["collections"][
        "basic_missions"
    ][0]["definition"]
    mission["successPoint"] = 0.6
    edited["fingerprint"] = digest(
        {"version": edited["version"], "payload": edited["payload"]}
    )

    original_report = export_review(raw)
    edited_report = export_review(edited)

    assert edited_report["input_identity"]["identity"]["artifact_fingerprint"] != (
        original_report["input_identity"]["identity"]["artifact_fingerprint"]
    )
    assert edited_report["view_fingerprint"] != original_report["view_fingerprint"]
    assert edited_report["export_fingerprint"] != original_report["export_fingerprint"]
    parameter = next(
        row
        for row in edited_report["views"]["parameters"]
        if row["logical_path"] == "successPoint"
    )
    assert parameter["value"] == 0.6
