"""Independent adversarial controls for the bounded offline trace query API."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.trace_query import query_trace

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "identity_contract"
LIMITATION = "unsigned_continuous_tail_deletion_undetectable"


def load(case: str, layer: str):
    return json.loads((FIXTURES / case / f"{layer}.json").read_text())


@pytest.fixture(scope="module")
def plan():
    return ExecutionPlan.from_dict(load("b1", "plan"))


@pytest.fixture(scope="module")
def result(plan):
    value = SimpyReferenceRuntime(plan, seed=7).run()
    value["sample_index"] = 0
    value["semantic_profile"] = plan.semantic_profile
    return value


def request(**overrides):
    value = {
        "run_id": "run-a",
        "sample_index": 0,
        "seed": 7,
        "backend": "python-reference",
    }
    value.update(overrides)
    return value


def codes(report):
    return {item["code"] for item in report["diagnostics"]}


def event_bytes(events):
    return len(
        json.dumps(
            events,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def assert_partial_envelope(report):
    assert report["schema_version"] == "simulation-trace-query/v1"
    assert report["status"] == "partial"
    assert LIMITATION in report["limitations"]
    assert report["coverage"]["level"] in {"partial", "none"}


@pytest.mark.parametrize(
    "query",
    [
        {"limit": 1},
        {"entity": "does-not-match"},
        {"limit": 1000, "max_event_bytes": 2},
    ],
    ids=("outside-page", "outside-filter", "outside-budget"),
)
def test_invalid_event_details_are_rejected_before_selection(plan, result, query) -> None:
    malformed = copy.deepcopy(result)
    malformed["trace"][1]["details"] = ["invalid-runtime-event-details"]

    report = query_trace(malformed, request(), plan, query=query)

    assert report["status"] == "invalid"
    assert report["events"] == []
    assert "unparseable_trace" in codes(report)
    assert report["diagnostics"][-1]["path"] == "result.trace[1].details"


def test_default_query_preserves_original_sequence_ids_and_recorded_facts(result, plan):
    result_before = copy.deepcopy(result)
    plan_before = copy.deepcopy(plan.to_dict())
    report = query_trace(result, request(), plan)

    assert_partial_envelope(report)
    assert report["coverage"]["input_event_count"] == len(result["trace"])
    assert report["coverage"]["matched_event_count"] == len(result["trace"])
    assert report["coverage"]["selected_event_count"] == len(result["trace"])
    assert [row["recorded_sequence"] for row in report["events"]] == list(
        range(1, len(result["trace"]) + 1)
    )
    for projected, recorded in zip(report["events"], result["trace"], strict=True):
        assert projected["time"] == recorded["time"]
        assert projected["kind"] == recorded["kind"]
        assert projected["recorded_references"] == {
            key: recorded.get(key) for key in ("rule_id", "entity", "source_path")
        }
        assert projected["trigger_relation"]["status"] == "unknown"
        assert projected["trigger_relation"]["event_ids"] == []
    assert result == result_before
    assert plan.to_dict() == plan_before


@pytest.mark.parametrize(
    ("bad_request", "bad_query", "expected_code"),
    [
        ({"sample_index": True}, None, "invalid_query_input"),
        ({"seed": False}, None, "invalid_query_input"),
        ({"horizon": True}, None, "invalid_query_input"),
        ({"unexpected": 1}, None, "invalid_query_input"),
        ({}, {"offset": True}, "invalid_query_input"),
        ({}, {"limit": False}, "invalid_query_input"),
        ({}, {"max_event_bytes": True}, "invalid_query_input"),
        ({}, {"time_start": True}, "invalid_query_input"),
        ({}, {"time_end": False}, "invalid_query_input"),
        ({}, {"unknown_filter": "x"}, "invalid_query_input"),
        ({}, {"resolve_event_ids": ["event:x"] * 33}, "invalid_query_input"),
        ({}, {"resolve_event_ids": ["event:x"]}, "invalid_query_input"),
        ({}, {"resolve_event_ids": [1]}, "invalid_query_input"),
        ({}, {"offset": -1}, "invalid_query_input"),
        ({}, {"limit": 1001}, "invalid_query_input"),
        ({}, {"max_event_bytes": 1}, "invalid_query_input"),
        ({}, {"time_start": 2, "time_end": 1}, "invalid_query_input"),
        ({"source_truncated": 1}, None, "invalid_query_input"),
    ],
)
def test_malformed_or_unknown_request_and_query_fields_fail_closed(
    result, plan, bad_request, bad_query, expected_code
):
    supplied_request = request(**bad_request)

    report = query_trace(result, supplied_request, plan, query=bad_query)

    assert report["status"] == "invalid"
    assert expected_code in codes(report)
    assert report["events"] == []


def test_non_python_backend_is_explicitly_unsupported(result, plan):
    report = query_trace(result, request(backend="rust-runtime"), plan)

    assert report["status"] == "unsupported"
    assert "unsupported_backend" in codes(report)
    assert report["events"] == []


def test_wrong_plan_and_mixed_bundle_revision_do_not_publish_events(result, plan):
    wrong_plan = load("f35", "plan")
    wrong = query_trace(result, request(), wrong_plan)
    mixed_bundle = {layer: load("f35", layer) for layer in (
        "business", "core", "plan", "lineage"
    )}
    mixed = query_trace(result, request(), plan, bundle=mixed_bundle)

    assert wrong["status"] == "invalid"
    assert "result_plan_mismatch" in codes(wrong)
    assert wrong["events"] == []
    assert mixed["status"] == "invalid"
    assert codes(mixed) & {"invalid_bundle", "plan_fingerprint_mismatch"}
    assert mixed["events"] == []


@pytest.mark.parametrize("bundle_case", ["b1", "f35"])
def test_missing_result_plan_hash_never_authorizes_design_links(
    result, bundle_case
):
    raw = copy.deepcopy(result)
    raw.pop("plan_fingerprint")
    persisted = {
        layer: load(bundle_case, layer)
        for layer in ("business", "core", "plan", "lineage")
    }

    report = query_trace(
        raw,
        request(),
        persisted["plan"],
        bundle=persisted,
    )

    assert_partial_envelope(report)
    assert report["events"]
    assert "result_plan_binding_insufficient" in codes(report)
    assert "plan_fingerprint" not in report["evidence_binding"][
        "verified_result_fields"
    ]
    assert all(
        row["facts"]["design_links"] == {"status": "unavailable", "links": []}
        for row in report["events"]
    )


def test_missing_plan_is_partial_and_never_inferred_from_result(result):
    report = query_trace(result, request(), None)

    assert_partial_envelope(report)
    assert "missing_plan" in codes(report)
    assert report["events"] == []
    assert report["coverage"]["level"] == "none"


def test_missing_lineage_cannot_authorize_design_links(result, plan):
    persisted = {
        layer: load("b1", layer) for layer in ("business", "core", "plan")
    }

    report = query_trace(result, request(), plan, bundle=persisted)

    assert_partial_envelope(report)
    assert report["review_identity"]["association_status"] == "partial"
    assert "lineage_missing" in codes(report)
    assert report["events"]
    assert all(
        row["facts"]["design_links"] == {"status": "unavailable", "links": []}
        for row in report["events"]
    )


def test_sequence_gap_and_reordering_are_partial_but_duplicate_is_invalid(result, plan):
    deleted = copy.deepcopy(result)
    del deleted["trace"][2]
    reordered = copy.deepcopy(result)
    reordered["trace"][0], reordered["trace"][1] = (
        reordered["trace"][1],
        reordered["trace"][0],
    )
    duplicate = copy.deepcopy(result)
    duplicate["trace"][1]["sequence"] = duplicate["trace"][0]["sequence"]

    deleted_report = query_trace(deleted, request(), plan)
    reordered_report = query_trace(reordered, request(), plan)
    duplicate_report = query_trace(duplicate, request(), plan)

    assert_partial_envelope(deleted_report)
    assert "trace_sequence_incomplete" in codes(deleted_report)
    assert_partial_envelope(reordered_report)
    assert "trace_sequence_reordered" in codes(reordered_report)
    assert duplicate_report["status"] == "invalid"
    assert "unparseable_trace" in codes(duplicate_report)
    assert duplicate_report["events"] == []


def test_unsigned_continuous_tail_deletion_is_declared_but_not_falsely_detected(result, plan):
    shortened = copy.deepcopy(result)
    shortened["trace"].pop()

    report = query_trace(shortened, request(), plan)

    assert_partial_envelope(report)
    assert report["coverage"]["input_event_count"] == len(result["trace"]) - 1
    assert "trace_sequence_incomplete" not in codes(report)
    assert "trace_sequence_reordered" not in codes(report)


def test_caller_declared_source_truncation_remains_partial_unknown_tail(result, plan):
    report = query_trace(result, request(source_truncated=True), plan)

    assert_partial_envelope(report)
    assert report["coverage"]["source"]["reason"] == "trace_truncated"
    assert "evidence_insufficient" in codes(report)


@pytest.mark.parametrize(
    ("observation", "remove_trace", "expected_reason"),
    [("summary", True, "summary_observation"), ("full", True, "trace_not_captured")],
)
def test_summary_and_missing_trace_return_empty_partial_evidence(
    result, plan, observation, remove_trace, expected_reason
):
    raw = copy.deepcopy(result)
    if remove_trace:
        raw.pop("trace")

    report = query_trace(raw, request(observation=observation), plan)

    assert_partial_envelope(report)
    assert report["events"] == []
    assert report["coverage"]["level"] == "none"
    assert report["coverage"]["source"]["reason"] == expected_reason
    assert "evidence_insufficient" in codes(report)


def test_entity_rule_event_and_half_open_time_filters_are_exact(result, plan):
    complete = query_trace(result, request(), plan)
    first = complete["events"][0]

    by_entity = query_trace(
        result,
        request(),
        plan,
        query={"entity": first["recorded_references"]["entity"]},
    )
    by_rule = query_trace(
        result,
        request(),
        plan,
        query={"rule_id": first["recorded_references"]["rule_id"]},
    )
    by_event = query_trace(
        result, request(), plan, query={"event_id": first["event_id"]}
    )
    by_time = query_trace(
        result, request(), plan, query={"time_start": 10, "time_end": 13}
    )

    assert all(
        row["recorded_references"]["entity"]
        == first["recorded_references"]["entity"]
        for row in by_entity["events"]
    )
    assert all(
        row["recorded_references"]["rule_id"]
        == first["recorded_references"]["rule_id"]
        for row in by_rule["events"]
    )
    assert [row["event_id"] for row in by_event["events"]] == [first["event_id"]]
    assert by_time["events"]
    assert all(10 <= row["time"] < 13 for row in by_time["events"])
    assert all(row["time"] != 13 for row in by_time["events"])


def test_run_sample_and_process_filters_never_cross_identity(result, plan):
    complete = query_trace(result, request(), plan)
    process_event = next(
        row
        for row in complete["events"]
        if row["facts"].get("process", {}).get("reference")
    )
    process = process_event["facts"]["process"]["reference"]

    matching = query_trace(
        result,
        request(),
        plan,
        query={"run_id": "run-a", "sample_index": 0, "process": process},
    )
    other_run = query_trace(result, request(), plan, query={"run_id": "run-b"})
    other_sample = query_trace(result, request(), plan, query={"sample_index": 1})

    assert matching["events"]
    assert all(
        row["facts"]["process"]["reference"] == process
        for row in matching["events"]
    )
    assert other_run["events"] == []
    assert other_sample["events"] == []


def test_pagination_preserves_ids_and_accounts_for_every_recorded_event(result, plan):
    complete = query_trace(result, request(), plan)
    page = query_trace(result, request(), plan, query={"offset": 2, "limit": 3})

    assert [row["event_id"] for row in page["events"]] == [
        row["event_id"] for row in complete["events"][2:5]
    ]
    coverage = page["coverage"]
    assert coverage["input_event_count"] == len(result["trace"])
    assert coverage["matched_event_count"] == len(result["trace"])
    assert coverage["selected_event_count"] == 3
    assert coverage["omitted_by_page"] == len(result["trace"]) - 3
    assert coverage["omitted_event_count"] == (
        coverage["omitted_by_filter"]
        + coverage["omitted_by_page"]
        + coverage["omitted_by_budget"]
    )


def test_canonical_array_byte_budget_is_strict_and_prefix_preserving(result, plan):
    complete = query_trace(result, request(), plan)
    first_size = event_bytes(complete["events"][:1])

    exact = query_trace(
        result, request(), plan, query={"max_event_bytes": first_size}
    )
    too_small = query_trace(
        result, request(), plan, query={"max_event_bytes": first_size - 1}
    )

    assert len(exact["events"]) == 1
    assert exact["events"][0]["event_id"] == complete["events"][0]["event_id"]
    assert event_bytes(exact["events"]) <= first_size
    assert exact["coverage"]["budget_exhausted"] is True
    assert too_small["events"] == []
    assert event_bytes(too_small["events"]) == 2
    assert too_small["coverage"]["budget_exhausted"] is True
    assert too_small["coverage"]["omitted_by_budget"] == len(result["trace"])


def test_resolution_distinguishes_selected_filter_page_budget_missing_and_cross_sample(
    result, plan
):
    complete = query_trace(result, request(), plan)
    ids = [row["event_id"] for row in complete["events"]]
    other = query_trace(result, request(run_id="run-b"), plan)
    other_id = other["events"][0]["event_id"]
    different_entity = next(
        row
        for row in complete["events"]
        if row["recorded_references"]["entity"]
        != complete["events"][0]["recorded_references"]["entity"]
    )
    shortened = copy.deepcopy(result)
    shortened["trace"].pop()
    cases = [
        (
            query_trace(
                result, request(), plan, query={"resolve_event_ids": [ids[0]]}
            ),
            ids[0],
            "selected",
            "selected",
        ),
        (
            query_trace(
                result,
                request(),
                plan,
                query={
                    "entity": complete["events"][0]["recorded_references"]["entity"],
                    "resolve_event_ids": [different_entity["event_id"]],
                },
            ),
            different_entity["event_id"],
            "omitted",
            "filter",
        ),
        (
            query_trace(
                result,
                request(),
                plan,
                query={"offset": 1, "limit": 1, "resolve_event_ids": ids[:2]},
            ),
            ids[0],
            "omitted",
            "page",
        ),
        (
            query_trace(
                result,
                request(),
                plan,
                query={"max_event_bytes": 2, "resolve_event_ids": [ids[0]]},
            ),
            ids[0],
            "omitted",
            "budget",
        ),
        (
            query_trace(
                shortened,
                request(),
                plan,
                query={"resolve_event_ids": [ids[-1]]},
            ),
            ids[-1],
            "not_recorded",
            "reference_unresolved",
        ),
        (
            query_trace(
                result,
                request(),
                plan,
                query={"resolve_event_ids": [other_id]},
            ),
            other_id,
            "cross_sample",
            "cross_sample_event_reference",
        ),
    ]

    for report, event_id, status, reason in cases:
        match = next(row for row in report["resolutions"] if row["event_id"] == event_id)
        assert match["status"] == status
        assert match["reason"] == reason


def test_unknown_event_kind_is_capability_limited_without_inventing_causality(result, plan):
    raw = copy.deepcopy(result)
    raw["trace"][0]["kind"] = "future_event_kind"

    report = query_trace(raw, request(), plan)

    assert report["status"] in {"partial", "unsupported"}
    if report["events"]:
        event = report["events"][0]
        assert event["trigger_relation"]["status"] == "unknown"
        assert event["trigger_relation"]["event_ids"] == []
        assert event["facts"]["status"] == "capability_limited"
        assert "event_kind_capability_limited" in {
            gap["code"] for gap in event["facts"]["evidence_gaps"]
        }
