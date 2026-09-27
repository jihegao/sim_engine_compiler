"""Review envelope and admission; identity authority remains identity.artifacts."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sim_engine_compiler.identity.artifacts import inspect_artifact, inspect_bundle
from sim_engine_compiler.identity.common import content_digest, diagnostic, json_value
from sim_engine_compiler.ir.layers import (
    BUSINESS_VERSION,
    CORE_VERSION,
    PROFILES,
    operation_contracts,
)
from sim_engine_compiler.ir.plan import PLAN_VERSION

from .views import project_views

SCHEMA_VERSION = "model-review-data/v1"
EXPORTER_VERSION = "review-exporter/v1"
VIEWS = ("entities", "relations", "processes", "states", "rules", "resources", "parameters")
LAYERS = ("business", "core", "plan", "lineage")


def support_matrix() -> dict[str, Any]:
    return {
        "primary_artifacts": [BUSINESS_VERSION, CORE_VERSION],
        "bundle_only_artifacts": [PLAN_VERSION, "compiler-lineage/v2"],
        "domain": "aircraft-support", "profiles": list(PROFILES), "views": list(VIEWS),
        "operations": [operation["operation"] for operation in operation_contracts()],
        "operation_precision": "conservative-phase; partial domain-rule coverage",
        "value_origin_vocabulary": ["explicit", "default", "normalized", "derived", "unknown"],
        "excluded": ["indexed-plan", "production", "abm", "sysml", "runtime-trace", "future-trajectories"],
    }


def _finish(report):
    report["diagnostics"] = [dict(item, reason=item.get("reason", item["message"]))
                             for item in report["diagnostics"]]
    report["view_fingerprint"] = content_digest(report["views"])
    report["export_fingerprint"] = content_digest(report)
    return report


def _envelope():
    return {"schema_version": SCHEMA_VERSION, "exporter_version": EXPORTER_VERSION,
            "status": "invalid", "support": support_matrix(), "input_identity": None,
            "bundle_identity": None, "association_status": "unverified",
            "views": {}, "mappings": {"business_to_core": [], "core_to_plan": []},
            "coverage": {"level": "none"}, "diagnostics": []}


def input_error_report(error):
    """Use the same versioned envelope for CLI load failures and API failures."""
    report = _envelope()
    report["diagnostics"].append(diagnostic(
        "review_input_read_error", str(error), stage="load", path="$input"))
    return _finish(report)


def export_review(value: Mapping[str, Any], *, bundle=None, views=None) -> dict[str, Any]:
    """Export reloaded Business/Core without original canonical input or execution.

    ``bundle`` is an optional raw dictionary of persisted business/core/plan/
    lineage artifacts, not an identity report. Every published cross-layer map
    requires the public bundle inspector's complete verified association.
    Valid inputs remain partial because provenance and domain-rule granularity
    cannot be reconstructed from these compatibility artifacts.
    """
    report = _envelope()
    try:
        raw = json_value(value)
        if views is None:
            selected = list(VIEWS)
        elif (type(views) is list and views and all(type(name) is str for name in views)
              and len(set(views)) == len(views) and set(views) <= set(VIEWS)):
            selected = [name for name in VIEWS if name in views]
        else:
            report["status"] = "unsupported"
            report["diagnostics"].append(diagnostic(
                "unsupported_review_views", "views must be a nonempty unique list of supported names",
                stage="review-selection", path="views"))
            return _finish(report)
        artifact = inspect_artifact(raw)
        report["input_identity"] = artifact
        report["diagnostics"].extend(artifact["diagnostics"])
        if artifact["status"] in ("invalid", "unsupported"):
            report["status"] = artifact["status"]
            return _finish(report)
        layer = artifact["layer"]
        if layer not in ("business", "core"):
            report["status"] = "unsupported"
            report["diagnostics"].append(diagnostic(
                "unsupported_review_primary_layer", "only persisted Business or Core is a primary review input",
                stage="review-admission", path="version"))
            return _finish(report)

        if bundle is not None:
            supplied = json_value(bundle)
            if not isinstance(supplied, dict) or not supplied or not set(supplied) <= set(LAYERS):
                report["diagnostics"].append(diagnostic(
                    "invalid_review_bundle", "bundle must contain only raw business/core/plan/lineage artifacts",
                    stage="bundle", path="bundle"))
                return _finish(report)
            if layer not in supplied or content_digest(supplied[layer]) != content_digest(raw):
                report["diagnostics"].append(diagnostic(
                    "review_primary_bundle_mismatch", "bundle primary layer must be the exact supplied review revision",
                    stage="bundle", path=f"bundle.{layer}"))
                return _finish(report)
            association = inspect_bundle(**supplied)
            report["bundle_identity"] = association
            report["diagnostics"].extend(association["diagnostics"])
            report["association_status"] = association["association_status"]
            if association["status"] in ("invalid", "unsupported"):
                report["status"] = association["status"]
                # The identity inspector may retain provisional mappings in an
                # invalid report; never publish those as review relationships.
                report["bundle_identity"] = {**association, "mappings": {"business_to_core": [], "core_to_plan": []}}
                return _finish(report)
            if association["association_status"] == "verified":
                report["mappings"] = json_value(association["mappings"])
            else:
                report["bundle_identity"] = {**association, "mappings": {"business_to_core": [], "core_to_plan": []}}
        else:
            report["diagnostics"].append(diagnostic(
                "review_bundle_missing", "standalone revision; no Business/Core/Plan association is inferred",
                stage="bundle", path="bundle", severity="warning"))

        projection = project_views(raw, artifact)
        report["views"] = {name: projection["views"][name] for name in selected}
        report["coverage"] = {**projection["coverage"], "level": "partial",
                              "selected_views": selected,
                              "omitted_views": [name for name in VIEWS if name not in selected]}
        report["diagnostics"].extend(projection["diagnostics"])
        report["diagnostics"].append(diagnostic(
            "review_provenance_partial", "producer versions, revision labels and value origins remain unknown when absent; "
            "persisted field presence and source paths do not prove explicitly supplied values",
            stage="provenance", path="input_identity.identity.producer", severity="warning"))
        if any(item["severity"] == "error" for item in report["diagnostics"]):
            report["status"] = "invalid"
            report["views"] = {}
            report["mappings"] = {"business_to_core": [], "core_to_plan": []}
            if report["bundle_identity"] is not None:
                report["bundle_identity"]["mappings"] = {"business_to_core": [], "core_to_plan": []}
        else:
            report["status"] = "partial"
    except (ValueError, TypeError, RecursionError, KeyError, IndexError) as error:
        report["status"] = "invalid"
        report["views"] = {}
        report["mappings"] = {"business_to_core": [], "core_to_plan": []}
        if report["bundle_identity"] is not None:
            report["bundle_identity"]["mappings"] = {"business_to_core": [], "core_to_plan": []}
        report["diagnostics"].append(diagnostic(
            "review_export_failed", str(error), stage="review-export", path="$"))
    return _finish(report)
