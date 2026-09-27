"""Offline trace selection. This module never imports or calls a runtime."""
from __future__ import annotations

import json
import math
from typing import Any

from sim_engine_compiler.identity import build_run_identity, project_event_references
from sim_engine_compiler.identity.common import content_digest, diagnostic, json_value
from sim_engine_compiler.review import export_review

from .facts import process_reference, project_facts

SCHEMA_VERSION = "simulation-trace-query/v1"
REQUEST_FIELDS = {
    "run_id", "sample_index", "seed", "backend", "observation", "horizon",
    "parameters", "engine_version", "domain_package_version", "source_truncated",
}
FILTER_FIELDS = {"run_id", "sample_index", "entity", "process", "rule_id", "event_id"}
QUERY_FIELDS = FILTER_FIELDS | {
    "time_start", "time_end", "offset", "limit", "max_event_bytes", "resolve_event_ids",
}
LIMITATIONS = [
    "unsigned_continuous_tail_deletion_undetectable",
    "caller_asserted_run_backend_and_sample_binding",
    "no_causality_inferred_from_event_adjacency",
    "unrecorded_guard_candidate_cache_and_trigger_state_unknown",
    "offline_event_payload_budget_not_runtime_collection_or_total_envelope_budget",
    "rust_collection_unsupported_in_this_slice",
]


def _envelope():
    return {
        "schema_version": SCHEMA_VERSION, "status": "invalid",
        "support": {"backends": ["python-reference"],
                    "profiles": ["legacy-minute-v1"],
                    "unsupported_profiles": ["event-time-v2"],
                    "observations": ["full", "summary-evidence-insufficient"],
                    "domain": "aircraft-support", "indexed_plan": False},
        "run_identity": None, "evidence_binding": None, "source_identity": None,
        "review_identity": None, "query": None, "events": [], "resolutions": [],
        "coverage": {"level": "none", "input_event_count": 0,
                     "matched_event_count": 0, "selected_event_count": 0,
                     "omitted_event_count": 0, "omitted_by_filter": 0,
                     "omitted_by_page": 0, "omitted_by_budget": 0,
                     "budget_exhausted": False, "source": None},
        "budget": None, "limitations": list(LIMITATIONS), "diagnostics": [],
    }


def _finish(report):
    report["content_digest"] = content_digest(report)
    return report


def input_error_report(error):
    report = _envelope()
    report["diagnostics"].append(diagnostic(
        "trace_query_input_read_error", str(error), stage="trace-query-load"))
    return _finish(report)


def _integer(value, low, high, field):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{field} must be an integer in [{low}, {high}]")


def _text(value, field):
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError(f"{field} must be a nonempty string of at most 4096 characters")


def _query(value):
    raw = {} if value is None else json_value(value)
    if type(raw) is not dict or not set(raw) <= QUERY_FIELDS:
        raise ValueError("query must contain only supported query fields")
    for key in FILTER_FIELDS - {"sample_index"}:
        if key in raw:
            _text(raw[key], f"query.{key}")
    if "sample_index" in raw:
        _integer(raw["sample_index"], 0, 2**63 - 1, "query.sample_index")
    for key in ("time_start", "time_end"):
        if key in raw and (type(raw[key]) not in (int, float)
                           or raw[key] < 0 or not math.isfinite(raw[key])):
            raise ValueError(f"query.{key} must be finite nonnegative time")
    if raw.get("time_start", 0) > raw.get("time_end", math.inf):
        raise ValueError("time_start must not exceed time_end; window is [start,end)")
    for key, default, low, high in (
        ("offset", 0, 0, 2**63 - 1), ("limit", 100, 0, 1000),
        ("max_event_bytes", 65536, 2, 1048576),
    ):
        raw.setdefault(key, default)
        _integer(raw[key], low, high, f"query.{key}")
    targets = raw.setdefault("resolve_event_ids", [])
    if (type(targets) is not list or len(targets) > 32
            or any(type(target) is not str for target in targets)
            or len(set(targets)) != len(targets)):
        raise ValueError("resolve_event_ids must be at most 32 unique event ID strings")
    for target in targets:
        _text(target, "resolve_event_ids")
        if not _event_id_shape(target):
            raise ValueError("resolve_event_ids contains a malformed event ID")
    if "event_id" in raw and not _event_id_shape(raw["event_id"]):
        raise ValueError("event_id must be a stable identity event ID")
    return raw


def _event_id_shape(value):
    parts = value.split(":")
    return (len(parts) == 3 and parts[0] == "event"
            and all(len(part) == 64 and all(c in "0123456789abcdef" for c in part)
                    for part in parts[1:]))


def _encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _matches(event, raw_event, identity, query):
    for key in ("run_id", "sample_index"):
        if key in query and query[key] != identity[key]:
            return False
    for key in ("entity", "rule_id"):
        if key in query and query[key] != event["recorded_references"][key]:
            return False
    if "event_id" in query and query["event_id"] != event["event_id"]:
        return False
    if "process" in query and query["process"] != process_reference(raw_event):
        return False
    return (event["time"] >= query.get("time_start", 0)
            and event["time"] < query.get("time_end", math.inf))


def _select(report, projection, raw, query, review):
    events = projection["events"]
    raw_by_sequence = ({event["sequence"]: event for event in raw["trace"]}
                       if events else {})
    matched = [event for event in events if _matches(
        event, raw_by_sequence[event["recorded_sequence"]],
        projection["run_identity"], query)]
    page = matched[query["offset"]:query["offset"] + query["limit"]]
    selected = []
    used_bytes = 2  # brackets of the canonical JSON event array
    for event in page:
        item = {**event, "facts": project_facts(
            raw_by_sequence[event["recorded_sequence"]], review=review)}
        size = len(_encoded(item)) + bool(selected)
        if used_bytes + size > query["max_event_bytes"]:
            break  # preserve a prefix; never skip a large item to include a later one
        selected.append(item)
        used_bytes += size
    report["events"] = selected
    report["budget"] = {
        "scope": "canonical_utf8_events_array_only", "used_event_bytes": used_bytes,
        "max_event_bytes": query["max_event_bytes"], "max_events": query["limit"],
        "runtime_collection_budget": False,
    }
    report["coverage"] = {
        "level": "none" if projection["coverage"]["level"] == "none" else "partial",
        "input_event_count": len(events), "matched_event_count": len(matched),
        "selected_event_count": len(selected), "omitted_event_count": len(events) - len(selected),
        "omitted_by_filter": len(events) - len(matched),
        "omitted_by_page": len(matched) - len(page),
        "omitted_by_budget": len(page) - len(selected),
        "budget_exhausted": len(page) > len(selected), "source": projection["coverage"],
    }
    if len(page) > len(selected):
        report["diagnostics"].append(diagnostic(
            "offline_output_budget_exhausted", "event array budget omitted the remaining page prefix",
            stage="trace-query", severity="warning"))
    matched_ids = {event["event_id"] for event in matched}
    page_ids = {event["event_id"] for event in page}
    selected_ids = {event["event_id"] for event in selected}
    index = {event["event_id"]: event["recorded_sequence"] for event in events}
    prefix = "event:" + projection["run_identity"]["sample_id"].removeprefix("sample:") + ":"
    targets = list(query["resolve_event_ids"])
    if "event_id" in query and query["event_id"] not in targets:
        targets.append(query["event_id"])
    for target in targets:
        if not target.startswith(prefix):
            status, reason = "cross_sample", "cross_sample_event_reference"
        elif target not in index:
            status, reason = "not_recorded", "reference_unresolved"
        elif target in selected_ids:
            status, reason = "selected", "selected"
        else:
            status = "omitted"
            reason = ("filter" if target not in matched_ids else
                      "page" if target not in page_ids else "budget")
        report["resolutions"].append({"event_id": target, "status": status,
                                      "reason": reason, "recorded_sequence": index.get(target)})


def query_trace(result: Any, request: Any, plan: Any, *, bundle=None, query=None):
    """Query persisted inputs without executing a simulation or modifying inputs.

    Request identity/backend is caller-asserted; recorded fields are cross-checked.
    A raw matching bundle is the only permitted authority for design associations.
    Budgets cap the canonical JSON selected event array, not total input, memory,
    CPU, envelope size, runtime collection or the original trace.
    """
    report = _envelope()
    stage = "request"
    try:
        req = json_value(request)
        if (type(req) is not dict or not set(req) <= REQUEST_FIELDS
                or not {"run_id", "sample_index", "seed", "backend"} <= set(req)):
            raise ValueError("request requires run_id/sample_index/seed/backend; unknown fields forbidden")
        _text(req["run_id"], "request.run_id")
        _text(req["backend"], "request.backend")
        _integer(req["sample_index"], 0, 2**63 - 1, "request.sample_index")
        _integer(req["seed"], 0, 2**64 - 1, "request.seed")
        if "horizon" in req:
            _integer(req["horizon"], 0, 2**63 - 1, "request.horizon")
        if type(req.get("observation", "full")) is not str or req.get("observation", "full") not in {"full", "summary"}:
            raise ValueError("request.observation must be full or summary")
        if "parameters" in req and type(req["parameters"]) is not dict:
            raise ValueError("request.parameters must be a JSON object")
        for field in ("engine_version", "domain_package_version"):
            if field in req:
                _text(req[field], f"request.{field}")
        if req["backend"] != "python-reference":
            report["status"] = "unsupported"
            report["diagnostics"].append(diagnostic(
                "unsupported_backend", "only Python reference recorded results are admitted; Rust unverified",
                stage="trace-query", path="request.backend"))
            return _finish(report)
        if "source_truncated" in req and type(req["source_truncated"]) is not bool:
            raise ValueError("source_truncated must be boolean")
        stage = "query"
        normalized = _query(query)
        report["query"] = normalized
        stage = "result"
        raw = json_value(result)
        if type(raw) is not dict:
            raise ValueError("result must be a persisted JSON object")
        for field in ("backend", "run_id", "observation"):
            expected = req.get(field, "full" if field == "observation" else None)
            if field in raw and (type(raw[field]) is not type(expected) or raw[field] != expected):
                raise ValueError(f"result.{field} does not match request")
        stage = "bundle"
        supplied = None if bundle is None else json_value(bundle)
        if supplied is not None and (type(supplied) is not dict or not supplied
                                    or not set(supplied) <= {"business", "core", "plan", "lineage"}):
            raise ValueError("bundle must contain only raw Business/Core/Plan/lineage artifacts")
        if plan is None:
            report["status"] = "partial"
            report["diagnostics"].append(diagnostic(
                "missing_plan", "validated Plan required to bind a legacy result; no Plan inferred",
                stage="trace-query", severity="warning"))
            return _finish(report)
        stage = "request"
        identity = build_run_identity(
            req["run_id"], req["sample_index"], req["seed"], plan, bundle=supplied,
            **{key: req[key] for key in ("observation", "horizon", "parameters",
                                       "engine_version", "domain_package_version") if key in req},
        )
        report["run_identity"] = identity
        report["diagnostics"].extend(identity["diagnostics"])
        if identity["status"] not in ("valid", "partial"):
            report["status"] = identity["status"]
            return _finish(report)
        if identity["execution_contract"]["semantic_profile"] != "legacy-minute-v1":
            report["status"] = "unsupported"
            report["diagnostics"].append(diagnostic(
                "unsupported_backend_profile", "Python reference does not collect event-time-v2 results",
                stage="trace-query", path="plan.semantic_profile"))
            return _finish(report)
        stage = "result"
        projection = project_event_references(
            identity, raw, truncated=req.get("source_truncated", False))
        report["diagnostics"].extend(projection["diagnostics"])
        if projection["status"] not in ("valid", "partial"):
            report["status"] = projection["status"]
            return _finish(report)
        report["source_identity"] = {"result_digest": content_digest(raw),
                                     "request_digest": content_digest(req),
                                     "identity_basis": "unsigned_supplied_content"}
        report["evidence_binding"] = {**projection["evidence_binding"],
                                      "backend": req["backend"], "backend_basis": "caller_asserted"}
        review = None
        if supplied is not None and supplied.get("core") is not None:
            stage = "review"
            review = export_review(supplied["core"], bundle=supplied)
            report["diagnostics"].extend(review["diagnostics"])
            if review["status"] not in ("valid", "partial"):
                report["status"] = review["status"]
                return _finish(report)
            report["review_identity"] = {
                "export_fingerprint": review["export_fingerprint"],
                "association_status": review["association_status"],
                "input_identity": review["input_identity"],
            }
        stage = "trace-query"
        linked_review = review
        if review is not None and "plan_fingerprint" not in projection["evidence_binding"]["verified_result_fields"]:
            linked_review = None
            report["diagnostics"].append(diagnostic(
                "result_plan_binding_insufficient", "result did not record a Plan fingerprint; "
                "a valid supplied design revision cannot authorize event-to-design links",
                stage="trace-query", severity="warning"))
        _select(report, projection, raw, normalized, linked_review)
        report["status"] = "partial"
        report["diagnostics"].append(diagnostic(
            "trace_evidence_partial", "only supplied recorded facts; unsigned tail completeness, "
            "unrecorded runtime causes and execution provenance remain unproven",
            stage="trace-query", severity="warning"))
    except (ValueError, TypeError, KeyError, IndexError, RecursionError, OverflowError) as error:
        report["status"] = "invalid"
        report["events"] = []
        report["resolutions"] = []
        report["diagnostics"].append(diagnostic(
            "invalid_query_input", str(error), stage="trace-query", path=stage))
    return _finish(report)
