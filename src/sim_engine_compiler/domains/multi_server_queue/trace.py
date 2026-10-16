"""Offline trace query for restricted queue results.

The query walks the supplied Business, Core, Plan, and lineage by recompiling
them. It does not execute the model. Design links are source-path matches
against that recompiled lineage, not causal edges. Python and Rust results use
the same event envelope, so both backends are admitted.
"""

from __future__ import annotations

import math
from typing import Any

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.identity.common import content_digest, diagnostic, json_value

from .model import PLAN_VERSION, QueueBusiness, lower

SCHEMA_VERSION = "simulation-trace-query/v1"
KNOWN_KINDS = frozenset({
    "customer_arrived",
    "service_started",
    "service_completed",
    "simulation_stopped",
})
QUERY_FIELDS = {
    "run_id", "sample_index", "entity", "process", "rule_id", "event_id",
    "time_start", "time_end", "offset", "limit", "max_event_bytes", "resolve_event_ids",
}
LIMITATIONS = [
    "unsigned_continuous_tail_deletion_undetectable",
    "caller_asserted_run_backend_and_sample_binding",
    "no_causality_inferred_from_event_adjacency",
    "unrecorded_guard_candidate_cache_and_trigger_state_unknown",
    "offline_event_payload_budget_not_runtime_collection_or_total_envelope_budget",
    "restricted_two_server_queue_profile",
    "queue_events_have_no_stable_event_id",
]


def _envelope() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "invalid",
        "support": {
            "backends": ["python-reference", "rust-runtime"],
            "profiles": ["event-time-queue-v1"],
            "unsupported_profiles": [],
            "observations": ["full", "summary-evidence-insufficient"],
            "domain": "multi-server-queue",
            "indexed_plan": False,
        },
        "run_identity": None,
        "evidence_binding": None,
        "source_identity": None,
        "review_identity": None,
        "query": None,
        "events": [],
        "resolutions": [],
        "coverage": {
            "level": "none",
            "input_event_count": 0,
            "matched_event_count": 0,
            "selected_event_count": 0,
            "omitted_event_count": 0,
            "omitted_by_filter": 0,
            "omitted_by_page": 0,
            "omitted_by_budget": 0,
            "budget_exhausted": False,
            "source": None,
        },
        "budget": None,
        "limitations": list(LIMITATIONS),
        "diagnostics": [],
    }


def _finish(report: dict[str, Any]) -> dict[str, Any]:
    report["content_digest"] = content_digest(report)
    return report


def _encoded(value: Any) -> bytes:
    import json
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _integer(value: Any, low: int, high: int, field: str) -> None:
    if type(value) is not int or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{field} must be an integer in [{low}, {high}]")


def _text(value: Any, field: str) -> None:
    if type(value) is not str or not value or len(value) > 4096:
        raise ValueError(f"{field} must be a nonempty string of at most 4096 characters")


def _normalize_query(query: Any) -> dict[str, Any]:
    raw = {} if query is None else query
    if not isinstance(raw, dict) or not set(raw) <= QUERY_FIELDS:
        raise ValueError("query must contain only supported query fields")
    for key in ("run_id", "entity", "process", "rule_id"):
        if key in raw:
            _text(raw[key], f"query.{key}")
    if "sample_index" in raw:
        _integer(raw["sample_index"], 0, 2**63 - 1, "query.sample_index")
    if "event_id" in raw:
        _text(raw["event_id"], "query.event_id")
    for key in ("time_start", "time_end"):
        if key in raw and (
            type(raw[key]) not in (int, float)
            or isinstance(raw[key], bool)
            or raw[key] < 0
            or not math.isfinite(raw[key])
        ):
            raise ValueError(f"query.{key} must be finite nonnegative time")
    if raw.get("time_start", 0) > raw.get("time_end", math.inf):
        raise ValueError("time_start must not exceed time_end; window is [start,end)")
    if "offset" in raw:
        _integer(raw["offset"], 0, 2**63 - 1, "query.offset")
    if "limit" in raw:
        _integer(raw["limit"], 0, 1000, "query.limit")
    if "max_event_bytes" in raw:
        _integer(raw["max_event_bytes"], 2, 1048576, "query.max_event_bytes")
    targets = raw.get("resolve_event_ids", [])
    if (
        type(targets) is not list
        or len(targets) > 32
        or any(type(target) is not str or not target for target in targets)
        or len(set(targets)) != len(targets)
    ):
        raise ValueError("resolve_event_ids must be at most 32 unique nonempty strings")
    return raw


def _select(events: list[dict[str, Any]], request: dict[str, Any], query: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    """Apply the supplied filters. Absent limit and budget keep the matched prefix."""
    matched = []
    for event in events:
        if query.get("run_id", request["run_id"]) != request["run_id"]:
            continue
        if query.get("sample_index", request["sample_index"]) != request["sample_index"]:
            continue
        if "entity" in query and query["entity"] != event["entity"]:
            continue
        if "rule_id" in query and query["rule_id"] != event["rule_id"]:
            continue
        if "process" in query and query["process"] != event["facts"]["process"]["reference"]:
            continue
        if "event_id" in query:
            continue
        start = query.get("time_start", 0)
        end = query.get("time_end", math.inf)
        if not (event["time"] >= start and event["time"] < end):
            continue
        matched.append(event)
    offset = query.get("offset", 0)
    limit = query.get("limit", len(matched))
    page = matched[offset:offset + limit]
    selected = []
    used_bytes = 2
    budget = "max_event_bytes" in query
    for event in page:
        size = len(_encoded(event)) + bool(selected)
        if budget and used_bytes + size > query["max_event_bytes"]:
            break
        selected.append(event)
        used_bytes += size
    coverage = {
        "level": "partial",
        "input_event_count": len(events),
        "matched_event_count": len(matched),
        "selected_event_count": len(selected),
        "omitted_event_count": len(events) - len(selected),
        "omitted_by_filter": len(events) - len(matched),
        "omitted_by_page": len(matched) - len(page),
        "omitted_by_budget": len(page) - len(selected),
        "budget_exhausted": len(page) > len(selected),
        "source": "queue-profile-recorded-events",
    }
    resolutions = [
        {
            "event_id": target,
            "status": "not_recorded",
            "reason": "queue_events_have_no_stable_event_id",
            "recorded_sequence": None,
        }
        for target in query.get("resolve_event_ids", [])
    ]
    if "event_id" in query and query["event_id"] not in query.get("resolve_event_ids", []):
        resolutions.append({
            "event_id": query["event_id"],
            "status": "not_recorded",
            "reason": "queue_events_have_no_stable_event_id",
            "recorded_sequence": None,
        })
    return selected, coverage, resolutions


def query_queue_trace(result: Any, request: dict[str, Any], plan: Any, *, bundle: Any = None, query: Any = None) -> dict[str, Any]:
    report = _envelope()
    try:
        raw_plan = json_value(plan)
        raw_result = json_value(result)
        raw_query = {} if query is None else json_value(query)
        if not isinstance(raw_plan, dict) or raw_plan.get("plan_version") != PLAN_VERSION:
            raise ValueError("queue plan version is required")
        if not isinstance(raw_result, dict):
            raise ValueError("result must be a persisted JSON object")
        for field in ("backend", "run_id", "observation"):
            expected = request.get(field, "full" if field == "observation" else None)
            if field in raw_result and raw_result[field] != expected:
                raise ValueError(f"result.{field} does not match request")
        if request.get("observation", "full") == "summary" or raw_result.get("observation") == "summary":
            report["status"] = "partial"
            report["diagnostics"].append(diagnostic(
                "summary_observation",
                "summary observation does not contain event evidence",
                stage="trace-query",
                severity="warning",
                path="result.trace",
            ))
            return _finish(report)
        supplied = None if bundle is None else json_value(bundle)
        if supplied is not None and (
            not isinstance(supplied, dict)
            or not supplied
            or not set(supplied) <= {"business", "core", "plan", "lineage"}
        ):
            raise ValueError("bundle must contain only raw Business/Core/Plan/lineage artifacts")
        linked = None
        if supplied and {"business", "core", "plan", "lineage"} <= set(supplied):
            business = QueueBusiness.from_dict(supplied["business"])
            core, lowered_plan, lineage = lower(business)
            if supplied["core"] != core or supplied["plan"] != lowered_plan or supplied["lineage"] != lineage:
                raise ValueError("bundle layers do not recompile to one queue revision")
            if lowered_plan != raw_plan:
                raise ValueError("query plan does not match the bundle plan")
            linked = {"business": business, "core": core, "plan": lowered_plan, "lineage": lineage}
        elif supplied is not None:
            raise ValueError("queue design links require business, core, plan, and lineage together")
        from sim_engine_compiler.identity.common import content_digest as digest
        if raw_result.get("plan_fingerprint") != digest(raw_plan):
            raise ValueError("result plan fingerprint does not match the supplied plan")
        if linked is not None:
            for field, expected in (
                ("business_fingerprint", linked["business"].fingerprint),
                ("core_fingerprint", linked["core"]["fingerprint"]),
            ):
                if raw_result.get(field) != expected:
                    raise ValueError(f"result {field} does not match the supplied bundle")
        trace = raw_result.get("trace")
        if not isinstance(trace, list):
            raise ValueError("trace must be a list")
        horizon = request.get("horizon", raw_plan["horizon_minutes"])
        symbols = linked["lineage"]["symbols"] if linked else []
        by_source = {}
        for symbol in symbols:
            by_source.setdefault(symbol["source_path"], symbol)
        events = []
        for index, event in enumerate(trace):
            if not isinstance(event, dict):
                raise ValueError(f"trace event {index} must be an object")
            for field in ("sequence", "time", "phase", "kind", "rule_id", "entity", "source_path"):
                if field not in event:
                    raise ValueError(f"trace event {index} is missing {field}")
            time = event["time"]
            if type(time) not in (int, float) or isinstance(time, bool) or not math.isfinite(time) or time < 0:
                raise ValueError(f"trace event {index} has a non-finite time")
            if horizon is not None and time > horizon:
                raise ValueError(f"trace event {index} is outside the requested horizon")
            symbol = by_source.get(event["source_path"])
            known = event["kind"] in KNOWN_KINDS
            if linked is None or symbol is None:
                design = {"status": "unavailable", "links": []}
            else:
                design = {
                    "status": "verified",
                    "links": [{
                        "business_path": symbol["source_path"],
                        "core_path": symbol["core_path"],
                        "plan_path": symbol["plan_path"],
                        "symbol_id": symbol["id"],
                    }],
                }
            events.append({
                "sequence": event["sequence"],
                "time": time,
                "phase": event["phase"],
                "kind": event["kind"],
                "rule_id": event["rule_id"],
                "entity": event["entity"],
                "source_path": event["source_path"],
                "facts": {
                    "schema_version": "trace-event-facts/v1",
                    "status": "recorded" if known else "capability_limited",
                    "recorded": {
                        "kind": event["kind"],
                        "rule_id": event["rule_id"],
                        "entity": event["entity"],
                        "source_path": event["source_path"],
                        "details": event.get("details"),
                    },
                    "process": {
                        "status": "recorded",
                        "reference": event["entity"],
                        "basis": "recorded.entity",
                    },
                    "design_links": design,
                    "evidence_gaps": [{
                        "code": "trigger_not_recorded",
                        "field": "trigger",
                        "reason": "queue events do not record a triggering event reference",
                    }],
                },
            })
        normalized = _normalize_query(raw_query)
        selected, coverage, resolutions = _select(events, request, normalized)
        report["query"] = normalized
        report["events"] = selected
        report["resolutions"] = resolutions
        report["run_identity"] = {
            "run_id": request["run_id"],
            "sample_index": request["sample_index"],
            "seed": request["seed"],
            "backend": request["backend"],
            "backend_basis": "caller_asserted",
        }
        report["evidence_binding"] = {
            "plan_fingerprint": raw_result.get("plan_fingerprint"),
            "business_fingerprint": raw_result.get("business_fingerprint"),
            "core_fingerprint": raw_result.get("core_fingerprint"),
            "verified_result_fields": [
                field for field in ("plan_fingerprint", "business_fingerprint", "core_fingerprint", "seed")
                if field in raw_result
            ],
            "binding_strength": "recompiled_bundle" if linked else "plan_fingerprint_cross_checked",
            "proves_runtime_consumed_plan": False,
            "backend": request["backend"],
            "backend_basis": "caller_asserted",
        }
        report["source_identity"] = {
            "result_digest": content_digest(raw_result),
            "request_digest": content_digest(request),
            "identity_basis": "unsigned_supplied_content",
        }
        if linked is not None:
            report["review_identity"] = {
                "association_status": "verified",
                "business_fingerprint": linked["business"].fingerprint,
                "core_fingerprint": linked["core"]["fingerprint"],
                "plan_fingerprint": content_digest(linked["plan"]),
            }
        report["coverage"] = coverage
        report["status"] = "partial"
        report["diagnostics"].append(diagnostic(
            "trace_evidence_partial",
            "queue facts are the supplied recorded events linked through the recompiled Business, Core, and Plan; execution provenance stays caller-asserted",
            stage="trace-query",
            severity="warning",
        ))
    except (CompilationError, ValueError, TypeError, KeyError, IndexError, RecursionError) as error:
        report["status"] = "invalid"
        report["events"] = []
        report["diagnostics"].append(diagnostic(
            "invalid_query_input",
            getattr(error, "message", str(error)),
            stage="trace-query",
            path=getattr(error, "source_path", None),
        ))
    return _finish(report)
