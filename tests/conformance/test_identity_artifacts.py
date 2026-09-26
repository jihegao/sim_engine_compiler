from __future__ import annotations

import copy
import json
from pathlib import Path

from sim_engine_compiler.compiler.layout import compile_core
from sim_engine_compiler.compiler.layout import lineage as make_lineage
from sim_engine_compiler.identity.artifacts import inspect_artifact, inspect_bundle
from sim_engine_compiler.ir.layers import (
    BUSINESS_VERSION,
    CORE_VERSION,
    BusinessIR,
    CoreIR,
    digest,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "identity_contract"


def load_bundle(case: str = "b1") -> dict:
    root = FIXTURES / case
    return {
        name: json.loads((root / f"{name}.json").read_text())
        for name in ("business", "core", "plan", "lineage")
    }


def reseal_core(value: dict) -> dict:
    value["fingerprint"] = digest({"version": CORE_VERSION, "payload": value["payload"]})
    return value


def test_persisted_layers_and_complete_bundle_are_independently_verified() -> None:
    bundle = load_bundle()
    assert inspect_artifact(bundle["business"])["status"] == "valid"
    assert inspect_artifact(bundle["core"])["status"] == "partial"
    assert inspect_artifact(bundle["plan"])["status"] == "partial"
    assert inspect_artifact(bundle["lineage"])["status"] == "valid"

    report = inspect_bundle(**bundle)
    assert report["status"] == "partial"
    assert report["association_status"] == "verified"
    assert report["identity"]["verified_artifact_digests"].keys() == bundle.keys()
    assert report["mappings"]["business_to_core"]
    assert report["mappings"]["core_to_plan"]
    assert all("qualified_id" in target
               for mapping in report["mappings"]["business_to_core"]
               for target in mapping["core_elements"])


def test_core_is_valid_alone_but_not_silently_associated_with_old_business() -> None:
    bundle = load_bundle()
    edited = copy.deepcopy(bundle["core"])
    edited["payload"]["contract"]["duration_minutes"] += 1
    reseal_core(edited)
    assert inspect_artifact(edited)["status"] == "partial"
    report = inspect_bundle(business=bundle["business"], core=edited)
    assert report["status"] == "invalid"
    assert "business_core_revision_mismatch" in {item["code"] for item in report["diagnostics"]}


def test_cross_revision_layers_are_rejected_even_when_each_layer_is_valid() -> None:
    b1 = load_bundle("b1")
    f35 = load_bundle("f35")
    report = inspect_bundle(
        business=b1["business"], core=f35["core"],
        plan=f35["plan"], lineage=f35["lineage"],
    )
    assert report["status"] == "invalid"
    assert "business_core_revision_mismatch" in {item["code"] for item in report["diagnostics"]}


def test_layout_reorder_keeps_qualified_identities_but_is_not_declared_verified() -> None:
    bundle = load_bundle("f35")
    core_value = copy.deepcopy(bundle["core"])
    core_value["payload"]["tables"]["aircraft"].reverse()
    reseal_core(core_value)
    core = CoreIR.from_dict(core_value)
    plan = compile_core(core)
    business = BusinessIR.from_dict(bundle["business"])
    report = inspect_bundle(
        business=bundle["business"], core=core_value,
        plan=json.loads(json.dumps(plan.to_dict())),
        lineage=make_lineage(business, core, plan),
    )
    assert report["status"] == "partial"
    assert report["association_status"] == "partial"
    assert "business_core_layout_order_changed" in {
        item["code"] for item in report["diagnostics"]
    }
    ids = {item["element_id"] for item in report["layers"]["core"]["elements"]}
    assert "aircraft/F35-01" in ids


def test_unknown_operation_is_stably_unsupported() -> None:
    core = copy.deepcopy(load_bundle()["core"])
    core["payload"]["operations"][0]["operation"] = "aircraft.unknown/v1"
    reseal_core(core)
    report = inspect_artifact(core)
    assert report["status"] == "unsupported"
    assert report["diagnostics"][0]["code"] == "unsupported_operation"


def test_unknown_profile_and_domain_are_stably_unsupported() -> None:
    plan = copy.deepcopy(load_bundle()["plan"])
    plan["semantic_profile"] = "future-time-v9"
    profile = inspect_artifact(plan)
    assert profile["status"] == "unsupported"
    assert "unsupported_semantic_profile" in {item["code"] for item in profile["diagnostics"]}

    plan = copy.deepcopy(load_bundle()["plan"])
    plan["domain"] = "production"
    domain = inspect_artifact(plan)
    assert domain["status"] == "unsupported"
    assert "unsupported_plan_domain" in {item["code"] for item in domain["diagnostics"]}

    business = copy.deepcopy(load_bundle()["business"])
    business["payload"]["semantic_profile"] = "future-time-v9"
    business["fingerprint"] = digest({
        "version": BUSINESS_VERSION, "payload": business["payload"],
    })
    unsupported_business = inspect_artifact(business)
    assert unsupported_business["status"] == "unsupported"
    assert "unsupported_semantic_profile" in {
        item["code"] for item in unsupported_business["diagnostics"]
    }


def test_plan_type_coercion_and_unknown_fields_are_invalid() -> None:
    plan = copy.deepcopy(load_bundle()["plan"])
    plan["duration_minutes"] = True
    assert inspect_artifact(plan)["status"] == "invalid"

    plan = copy.deepcopy(load_bundle()["plan"])
    plan["invented"] = "field"
    assert inspect_artifact(plan)["status"] == "invalid"

    plan = copy.deepcopy(load_bundle()["plan"])
    plan["aircraft"][0]["index"] = True
    assert inspect_artifact(plan)["status"] == "invalid"


def test_resource_dispatch_index_is_explicitly_outside_v1_identity_validation() -> None:
    plan = copy.deepcopy(load_bundle()["plan"])
    plan["resource_dispatch_index"] = {"schema_version": "resource-dispatch-index/v2"}
    report = inspect_artifact(plan)
    assert report["status"] == "unsupported"
    assert "unsupported_resource_dispatch_index_identity_contract" in {
        item["code"] for item in report["diagnostics"]
    }


def test_lineage_requires_hex_fingerprints_and_canonical_symbol_shape() -> None:
    lineage = copy.deepcopy(load_bundle()["lineage"])
    lineage["core_fingerprint"] = "z" * 64
    report = inspect_artifact(lineage)
    assert report["status"] == "invalid"
    assert "invalid_lineage_fingerprint" in {item["code"] for item in report["diagnostics"]}

    lineage = copy.deepcopy(load_bundle()["lineage"])
    lineage["symbols"]["aircraft"][0]["plan_path"] = "aircraft[999]"
    report = inspect_artifact(lineage)
    assert report["status"] == "invalid"
    assert "invalid_lineage_symbol" in {item["code"] for item in report["diagnostics"]}


def test_lineage_fingerprint_or_symbol_tampering_invalidates_bundle() -> None:
    bundle = load_bundle()
    bundle["lineage"]["plan_fingerprint"] = "0" * 64
    report = inspect_bundle(**bundle)
    assert report["status"] == "invalid"
    assert "lineage_fingerprint_mismatch" in {item["code"] for item in report["diagnostics"]}


def test_missing_layers_are_partial_and_never_claim_plan_association() -> None:
    bundle = load_bundle()
    report = inspect_bundle(core=bundle["core"])
    assert report["status"] == "partial"
    assert report["association_status"] == "partial"
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}
    assert {item["code"] for item in report["diagnostics"]} >= {
        "business_missing", "plan_missing", "lineage_missing",
    }


def test_wrong_layer_slot_and_non_json_input_return_structured_invalid_results() -> None:
    bundle = load_bundle()
    wrong = inspect_bundle(business=bundle["core"])
    assert wrong["status"] == "invalid"
    assert "bundle_layer_mismatch" in {item["code"] for item in wrong["diagnostics"]}

    malformed = inspect_bundle(business={"version": BUSINESS_VERSION, "value": float("nan")})
    assert malformed["status"] == "invalid"
    assert malformed["identity"]["bundle_digest"] is None


def test_abm_artifact_is_explicitly_isolated_from_aircraft_contract() -> None:
    report = inspect_artifact({"version": "abm-business-ir/v1", "fingerprint": "x", "payload": {}})
    assert report["status"] == "unsupported"
    assert report["diagnostics"][0]["code"] == "unsupported_artifact_domain"


def test_source_paths_survive_without_inventing_value_provenance_or_producer() -> None:
    report = inspect_artifact(load_bundle()["business"])
    assert report["identity"]["producer"]["status"] == "unknown"
    assert all(item["provenance"]["source_path"] for item in report["elements"])
    assert {item["provenance"]["value_origin"] for item in report["elements"]} == {"unknown"}
    assert report["coverage"]["value_provenance_vocabulary"] == [
        "explicit", "default", "normalized", "derived", "unknown",
    ]
