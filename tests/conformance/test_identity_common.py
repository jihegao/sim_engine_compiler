import math

import pytest

from sim_engine_compiler.identity import (
    inspect_artifact,
    inspect_bundle,
    inspect_run_identity,
    project_event_references,
    resolve_event_reference,
)
from sim_engine_compiler.identity.common import content_digest, json_value


@pytest.mark.parametrize("value", [math.nan, math.inf, {1: "not-string"}, (1, 2), object()])
def test_non_json_values_are_not_coerced(value):
    with pytest.raises(ValueError):
        json_value(value)


def test_cycles_rejected_and_shared_values_copied_without_aliasing():
    cycle = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="cyclic"):
        json_value(cycle)
    shared = {"id": "stable"}
    result = json_value([shared, shared])
    assert result == [shared, shared]
    assert result[0] is not result[1]
    assert result[0] is not shared


def test_exact_content_digest_is_not_business_identity():
    assert content_digest({"a": 1, "b": 2}) == content_digest({"b": 2, "a": 1})
    assert content_digest([1, 2]) != content_digest([2, 1])
    assert content_digest(1) != content_digest(True)
    assert content_digest(1) != content_digest(1.0)


@pytest.mark.parametrize("value", [None, False, 0, 0.0, "", [], {}, [[]], {"x": math.nan}])
def test_public_inspectors_return_structured_results_for_malformed_values(value):
    reports = [
        inspect_artifact(value), inspect_bundle(core=value), inspect_run_identity(value),
        project_event_references(value, {}), resolve_event_reference(value, "event:x"),
    ]
    for report in reports:
        assert report["status"] in ("invalid", "unsupported", "partial")
        assert report["diagnostics"]
