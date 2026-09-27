from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.review import export_review

FIXTURES = Path(__file__).parents[1] / "fixtures/identity_contract"


def bundle(case="b1"):
    return {name: json.loads((FIXTURES / case / f"{name}.json").read_text())
            for name in ("business", "core", "plan", "lineage")}


@pytest.mark.parametrize("case", ["b1", "f35"])
@pytest.mark.parametrize("layer", ["business", "core"])
def test_export_reloaded_real_artifact_is_deterministic_and_never_mutates_input(case, layer):
    artifacts = bundle(case)
    before = copy.deepcopy(artifacts)
    first = export_review(artifacts[layer], bundle=artifacts)
    assert first == export_review(json.loads(json.dumps(artifacts[layer])), bundle=artifacts)
    assert first["schema_version"] == "model-review-data/v1"
    assert first["exporter_version"] == "review-exporter/v1"
    assert first["status"] == "partial"
    assert first["association_status"] == "verified"
    assert first["input_identity"]["identity"]["artifact_fingerprint"] == artifacts[layer]["fingerprint"]
    assert first["input_identity"]["identity"]["producer"]["compiler_version"] is None
    assert first["mappings"]["core_to_plan"]
    assert all(item["basis"] == "verified-compiler-lineage/v2" for item in first["mappings"]["core_to_plan"])
    assert first["view_fingerprint"] == content_digest(first["views"])
    unsigned = dict(first)
    unsigned.pop("export_fingerprint")
    assert first["export_fingerprint"] == content_digest(unsigned)
    assert artifacts == before


def test_selection_is_order_independent_and_only_changes_requested_projection():
    core = bundle()["core"]
    selected = export_review(core, views=["rules", "entities"])
    assert selected == export_review(core, views=["entities", "rules"])
    assert set(selected["views"]) == {"rules", "entities"}
    assert selected["coverage"]["selected_views"] == ["entities", "rules"]
    assert "resources" in selected["coverage"]["omitted_views"]
    assert selected["coverage"]["level"] == "partial"
    all_views = export_review(core)
    assert selected["views"]["rules"] == all_views["views"]["rules"]
    assert selected["view_fingerprint"] != all_views["view_fingerprint"]


@pytest.mark.parametrize("views", [[], ["future"], ["rules", "rules"], "rules", [1]])
def test_unknown_or_ambiguous_view_requests_fail_closed(views):
    report = export_review(bundle()["core"], views=views)
    assert report["status"] == "unsupported"
    assert report["views"] == {}


@pytest.mark.parametrize("value", [None, [], {"x": float("nan")}, {1: "non-string-key"}])
def test_invalid_json_or_non_artifact_is_structured(value):
    report = export_review(value)
    assert report["status"] in {"invalid", "unsupported"}
    assert report["views"] == {}
    assert all({"code", "severity", "stage", "path", "element_id", "reason"} <= set(item)
               for item in report["diagnostics"])


def test_inspector_report_is_not_accepted_as_raw_bundle():
    core = bundle()["core"]
    report = export_review(core, bundle={"schema_version": "model-bundle-identity/v1", "status": "verified"})
    assert report["status"] == "invalid"
    assert report["mappings"] == {"business_to_core": [], "core_to_plan": []}


def test_plan_only_input_cannot_be_misrepresented_as_design_ir():
    report = export_review(bundle()["plan"])
    assert report["status"] == "unsupported"
    assert report["views"] == {}
