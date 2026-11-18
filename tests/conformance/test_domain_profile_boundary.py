"""Domain-profile boundary and closed Business section vocabulary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.domains.multi_server_queue.model import EXAMPLE_INPUT
from sim_engine_compiler.domains.profiles import import_registered_canonical, registered_profiles
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.layers import BusinessIR
from sim_engine_compiler.product import ProductError, seal_business, validate_business

ROOT = Path(__file__).resolve().parents[2]
B1_BUSINESS = ROOT / "tests" / "fixtures" / "identity_contract" / "b1" / "business.json"
AIRCRAFT_FINGERPRINT = "58bc6d1abdc3339a071e387bd359ce92d7f22e57204182e30d991fc0e6b1e0de"


def test_registered_profiles_keep_aircraft_and_admit_the_queue_schema():
    assert registered_profiles() == ("aircraft-support-v1", "multi-server-queue-v1")
    business = import_registered_canonical(EXAMPLE_INPUT)
    encoded = json.dumps(business.to_dict())
    assert business.payload["profile"] == "multi-server-queue-v1"
    assert "tail_number" not in encoded
    assert "AC-00" not in encoded
    assert "resource_nodes" not in encoded


def test_aircraft_importer_still_rejects_a_non_aircraft_schema():
    with pytest.raises(CompilationError) as caught:
        import_business_ir(EXAMPLE_INPUT)
    assert caught.value.code != "unconsumed_business_section"
    assert "schema_version" in (caught.value.source_path or "")


def test_aircraft_b1_business_fingerprint_is_unchanged():
    raw = json.loads(B1_BUSINESS.read_text())
    loaded = BusinessIR.from_dict(raw)
    assert loaded.fingerprint == AIRCRAFT_FINGERPRINT
    assert loaded.fingerprint == raw["fingerprint"]
    report = validate_business(raw)
    assert report["status"] == "valid"
    assert report["identity"]["business_fingerprint"] == AIRCRAFT_FINGERPRINT


def test_validation_reports_aircraft_lowering_error_with_source_path():
    payload = json.loads(B1_BUSINESS.read_text())["payload"]
    activities = payload["sections"]["support_activities"]["collections"]["activities"]
    activities[0]["definition"]["jobs"][0]["durationMinutes"] = -1
    checked = validate_business(BusinessIR.create(payload).to_dict())
    assert checked["status"] == "invalid"
    (diagnostic,) = checked["diagnostics"]
    assert diagnostic["code"] == "negative_duration"
    assert diagnostic["stage"] == "validate"
    assert diagnostic["path"] == "support_activities.activities[0].jobs[0].durationMinutes"


def test_queue_payload_labeled_as_aircraft_fails_with_an_unconsumed_section():
    labeled = dict(EXAMPLE_INPUT)
    labeled["schema_version"] = "aircraft-support-v1-input-v1"
    with pytest.raises(ProductError) as caught:
        seal_business(labeled)
    error = caught.value
    assert error.code == "unconsumed_business_section"
    assert error.path == "business.sections.arrivals"
    assert error.message == "Business section 'arrivals' is not consumed by profile aircraft-support-v1"


def test_importer_rejects_queue_sections_on_the_aircraft_schema():
    labeled = dict(EXAMPLE_INPUT)
    labeled["schema_version"] = "aircraft-support-v1-input-v1"
    with pytest.raises(CompilationError) as caught:
        import_business_ir(labeled)
    assert caught.value.code == "unconsumed_business_section"
    assert caught.value.source_path == "business.sections.arrivals"
    assert caught.value.message == "Business section 'arrivals' is not consumed by profile aircraft-support-v1"
