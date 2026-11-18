"""Queue trace pages use the public default event and byte limits."""

import json

import pytest

from sim_engine_compiler.domains.multi_server_queue.model import EXAMPLE_INPUT, import_canonical, lower
from sim_engine_compiler.domains.multi_server_queue.runtime import execute
from sim_engine_compiler.trace_query import query_trace


def event_bytes(events):
    return len(json.dumps(
        events, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8"))


@pytest.fixture(scope="module")
def dense_trace():
    inputs = {**EXAMPLE_INPUT, "arrivals": {**EXAMPLE_INPUT["arrivals"], "rate_per_minute": 5.0}}
    _, plan, _ = lower(import_canonical(inputs))
    result = execute(plan, seed=0, sample_index=0)
    request = {"run_id": "dense-queue", "seed": 0, "sample_index": 0, "backend": "python-reference"}
    full = query_trace(result, request, plan, query={"limit": 1000, "max_event_bytes": 1_048_576})
    assert full["coverage"]["omitted_event_count"] == 0
    assert len(full["events"]) > 100
    return result, request, plan, full["events"]


@pytest.mark.parametrize("query, offset, limit, max_bytes", [
    ({}, 0, 100, 65_536),
    ({"offset": 3, "max_event_bytes": 1_048_576}, 3, 100, 1_048_576),
    ({"limit": 1000}, 0, 1000, 65_536),
])
def test_queue_trace_limits_return_the_longest_fitting_prefix(dense_trace, query, offset, limit, max_bytes):
    result, request, plan, full = dense_trace
    report = query_trace(result, request, plan, query=query)
    assert report["status"] == "partial"
    assert report["query"] == {"offset": offset, "limit": limit, "max_event_bytes": max_bytes}
    page = full[offset:offset + limit]
    events = report["events"]
    assert events == page[:len(events)]
    assert report["budget"] == {
        "scope": "canonical_utf8_events_array_only",
        "used_event_bytes": event_bytes(events),
        "max_event_bytes": max_bytes,
        "max_events": limit,
        "runtime_collection_budget": False,
    }
    assert event_bytes(events) <= max_bytes
    assert report["coverage"]["omitted_by_page"] == len(full) - len(page)
    assert report["coverage"]["omitted_by_budget"] == len(page) - len(events)
    if max_bytes == 65_536:
        assert report["coverage"]["budget_exhausted"]
        assert event_bytes(page[:len(events) + 1]) > max_bytes
        assert "offline_output_budget_exhausted" in {item["code"] for item in report["diagnostics"]}
    else:
        assert len(events) == 100
        assert not report["coverage"]["budget_exhausted"]
