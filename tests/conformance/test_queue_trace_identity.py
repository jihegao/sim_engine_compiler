"""Queue trace facts must match the recorded replication."""

import pytest

from sim_engine_compiler.domains.multi_server_queue.model import EXAMPLE_INPUT, import_canonical, lower
from sim_engine_compiler.domains.multi_server_queue.runtime import execute
from sim_engine_compiler.trace_query import query_trace


@pytest.fixture
def replication():
    business = import_canonical(EXAMPLE_INPUT)
    core, plan, lineage = lower(business)
    bundle = {"business": business.to_dict(), "core": core, "plan": plan, "lineage": lineage}
    request = {"run_id": "queue-trace", "seed": 0, "sample_index": 0, "backend": "python-reference"}
    return execute(plan, seed=0, sample_index=0), request, plan, bundle


@pytest.mark.parametrize(("field", "value"), [("seed", 7), ("sample_index", 99)])
def test_queue_trace_rejects_another_replication(replication, field, value):
    result, request, plan, _ = replication
    report = query_trace(result, {**request, field: value}, plan)
    assert report["status"] == "invalid"
    assert report["events"] == []
    assert report["run_identity"] is None
    assert report["evidence_binding"] is None
    assert report["diagnostics"][0]["path"] == f"result.{field}"


@pytest.mark.parametrize(
    ("field", "value"),
    [("seed", False), ("sample_index", 0.0), ("semantic_profile", "legacy-minute-v1")],
)
def test_queue_trace_rejects_invalid_recorded_identity(replication, field, value):
    result, request, plan, _ = replication
    report = query_trace({**result, field: value}, request, plan)
    assert report["status"] == "invalid"
    assert report["diagnostics"][0]["path"] == f"result.{field}"
    assert report["events"] == []


@pytest.mark.parametrize("field", ["seed", "sample_index", "semantic_profile"])
def test_queue_trace_requires_recorded_replication_fields(replication, field):
    result, request, plan, _ = replication
    del result[field]
    report = query_trace(result, request, plan)
    assert report["status"] == "invalid"
    assert report["diagnostics"][0]["path"] == f"result.{field}"
    assert report["events"] == []


def test_queue_trace_reports_only_actually_cross_checked_fields(replication):
    result, request, plan, bundle = replication
    report = query_trace(result, request, plan)
    assert report["status"] == "partial"
    assert report["events"]
    fields = {"plan_fingerprint", "seed", "sample_index", "semantic_profile"}
    assert set(report["evidence_binding"]["verified_result_fields"]) == fields

    linked = query_trace(result, request, plan, bundle=bundle)
    assert linked["status"] == "partial"
    assert linked["events"][0]["facts"]["design_links"]["status"] == "verified"
    assert set(linked["evidence_binding"]["verified_result_fields"]) == fields | {
        "business_fingerprint", "core_fingerprint",
    }
