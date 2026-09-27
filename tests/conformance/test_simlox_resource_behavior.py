from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "cases/simlox-air-support/preparation-resource-v1"
sys.path.insert(0, str(BUNDLE))


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, BUNDLE / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATE = load("simlox_resource_parse_events", "validate.py")
RESOURCES = load("simlox_resource_behavior", "validate_resources.py")
CONTRACT = json.loads((BUNDLE / "contracts/C03.json").read_text(encoding="utf-8"))


def local_probe(case_id: str, variant_id: str) -> tuple[str, dict, dict]:
    roots = sorted((ROOT / "data/local/issue18-native/f8b2face730d/v1" / case_id / variant_id).glob("*"))
    if len(roots) != 1:
        pytest.skip("sealed f8b2face native evidence is not present in this checkout")
    run = roots[0]
    raw = (run / "model.log").read_text(encoding="utf-8-sig")
    report_doc = json.loads(VALIDATE._remove_trailing_commas((run / "report-raw.json").read_bytes()))
    case_contract = json.loads((BUNDLE / f"contracts/{case_id}.json").read_text(encoding="utf-8"))
    return raw, report_doc, case_contract


def report(staffing: int) -> dict:
    first_wait = 0 if staffing == 2 else 1
    second_use = 0 if staffing == 2 else 1
    columns = ["RID", "STID", "STINT", "ETINT", "NR", "NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO"]
    resource_rows = [
        ["Total over all Resources", "Total over all Stations", 7.5, 8, staffing, 0, 0, staffing, 0, first_wait, staffing, staffing, 0, 0, 0, 0],
        ["Total over all Resources", "Total over all Stations", 8, 8.5, staffing, 0, 0, second_use, 0, 0, staffing, staffing, 0, 0, 0, 0],
    ]
    return {"report": {"tables": [
        {"name": "ResultSummary", "columns": [{"name": name} for name in ["NREP", "MSTF", "MSUF"]], "instances": [{"rows": [[1, 1, 1]]}]},
        {"name": "ResourceResults", "columns": [{"name": name} for name in columns], "instances": [{"rows": resource_rows}]},
    ]}}


def events(staffing: int) -> str:
    lines = [
        "Time: 7.5 <AIR-TYPE,0> preparation started, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>",
        "Time: 7.5 <AIR-TYPE,1> preparation started, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>",
        "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> started",
        "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> requests resources",
        "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> resource availability test",
        "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
        "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> books resources",
        f"Time: 7.5 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1 available now: {staffing - 1}",
        "Time: 7.5 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> starts performing, planned to last for 0.5 hours",
        "Time: 7.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> started",
        "Time: 7.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> requests resources",
    ]
    if staffing == 2:
        lines.extend([
            "Time: 7.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> resource availability test",
            "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
            "Time: 7.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> books resources",
            "Time: 7.5 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1 available now: 0",
            "Time: 7.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> starts performing, planned to last for 0.5 hours",
            "Time: 8 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> completed",
            "Time: 8 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> frees resources",
            "Time: 8 <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1 available now: 1",
            "Time: 8 system preparation task 0 on <AIR-TYPE,0> completed",
            "Time: 8 <AIR-TYPE,0> preparation ended, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>",
            "Time: 8 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> completed",
            "Time: 8 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> frees resources",
            "Time: 8 <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1 available now: 2",
            "Time: 8 system preparation task 1 on <AIR-TYPE,1> completed",
            "Time: 8 <AIR-TYPE,1> preparation ended, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>",
            "Time: 8 <FORMATION-TWO,FORMATION-UNIT,0,0,0> mission starting, duration: 1 : <AIR-TYPE,0>,<AIR-TYPE,1>",
            "Time: 9 <FORMATION-TWO,FORMATION-UNIT,0,0,0> mission completed: <AIR-TYPE,0>,<AIR-TYPE,1>",
        ])
    else:
        lines.extend([
            "Time: 7.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> resource availability test",
            "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed",
            "Time: 8 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> completed",
            "Time: 8 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> frees resources",
            "Time: 8 <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1 available now: 1",
            "Time: 8 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> resource availability test",
            "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK",
            "Time: 8 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> resource received",
            "Time: 8 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> books resources",
            "Time: 8 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1 available now: 0",
            "Time: 8 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> starts performing, planned to last for 0.5 hours",
            "Time: 8 system preparation task 0 on <AIR-TYPE,0> completed",
            "Time: 8 <AIR-TYPE,0> preparation ended, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>",
            "Time: 8.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> completed",
            "Time: 8.5 subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> frees resources",
            "Time: 8.5 <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1 available now: 1",
            "Time: 8.5 system preparation task 1 on <AIR-TYPE,1> completed",
            "Time: 8.5 <AIR-TYPE,1> preparation ended, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>",
            "Time: 8.5 <FORMATION-TWO,FORMATION-UNIT,0,0,0> mission starting, duration: 1 : <AIR-TYPE,0>,<AIR-TYPE,1>",
            "Time: 9.5 <FORMATION-TWO,FORMATION-UNIT,0,0,0> mission completed: <AIR-TYPE,0>,<AIR-TYPE,1>",
        ])
    return "\n".join(lines)


def test_c03_staffing_two_validates_parallel_owner_and_report_evidence():
    result = RESOURCES.validate_resource_behavior("C03", "staffing-2", events(2), report(2), CONTRACT)
    assert result["passed"], result["assertions"]
    assert result["status"] == "bounded_native_resource_behavior_verified"


def test_c03_staffing_one_validates_wait_regrant_and_delayed_launch():
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", events(1), report(1), CONTRACT)
    assert result["passed"], result["assertions"]


def test_wrong_launch_identity_is_rejected_even_with_correct_resource_totals():
    broken = events(1).replace(
        "mission starting, duration: 1 : <AIR-TYPE,0>,<AIR-TYPE,1>",
        "mission starting, duration: 1 : <AIR-TYPE,0>,<WRONG,1>",
    )
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report(1), CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "formation_launch_and_completion")["passed"]


def test_report_must_show_the_capacity_bounded_wait_interval():
    broken = report(1)
    resource = next(table for table in broken["report"]["tables"] if table["name"] == "ResourceResults")
    resource["instances"][0]["rows"][0][9] = 0
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", events(1), broken, CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "capacity_interval_report")["passed"]


def test_missing_untimestamped_availability_detail_is_rejected():
    broken = events(1).replace(
        "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed\n",
        "",
        1,
    )
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report(1), CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "second_owner_wait_regrant_ledger")["passed"]


def test_missing_deallocation_is_rejected():
    broken = events(1).replace(
        "Time: 8.5 <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1 available now: 1",
        "Time: 8.5 release detail missing",
    )
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report(1), CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "serial_capacity_ledger")["passed"]


def test_forged_success_summary_is_rejected():
    broken = report(1)
    summary = next(table for table in broken["report"]["tables"] if table["name"] == "ResultSummary")
    summary["instances"][0]["rows"][0] = [1, 0, 0]
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", events(1), broken, CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "mission_summary_correlates_with_enlog")["passed"]


def test_wrong_request_quantity_is_rejected():
    broken = events(1).replace("request for: 1 OK", "request for: 9 OK", 1)
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report(1), CONTRACT)
    assert not result["passed"]


def test_impossible_available_now_counter_is_rejected():
    broken = events(1).replace("available now: 1", "available now: 999")
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report(1), CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "serial_capacity_ledger")["passed"]


def test_staffing_one_accepts_the_other_native_owner_as_first_grant():
    swapped = events(1).replace("<AIR-TYPE,0>", "<AIR-TYPE,X>")
    swapped = swapped.replace("<AIR-TYPE,1>", "<AIR-TYPE,0>").replace("<AIR-TYPE,X>", "<AIR-TYPE,1>")
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", swapped, report(1), CONTRACT)
    assert result["passed"], result["assertions"]


def test_missing_outer_preparation_completion_is_rejected():
    broken = events(1).replace(
        "Time: 8 <AIR-TYPE,0> preparation ended, mission: <FORMATION-TWO,FORMATION-UNIT,0,0,0>\n",
        "",
    )
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report(1), CONTRACT)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "first_owner_ledger")["passed"]


def test_c01_wrong_requested_quantity_is_rejected_from_real_probe_shape():
    raw, report_doc, case_contract = local_probe("C01", "capacity-2")
    broken = raw.replace("request for: 2 OK", "request for: 9 OK", 1)
    result = RESOURCES.validate_resource_behavior("C01", "capacity-2", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "qualified_request_identity_and_quantity")["passed"]


def test_c02_missing_equipment_release_is_rejected_from_real_probe_shape():
    raw, report_doc, case_contract = local_probe("C02", "both-available")
    broken = raw.replace(
        "<E-GSE at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1",
        "<E-GSE at <BASE-01,0>> release detail missing",
        1,
    )
    result = RESOURCES.validate_resource_behavior("C02", "both-available", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "joint_grant_and_release")["passed"]


def test_c01_positive_requires_full_owner_work_lifecycle():
    raw, report_doc, case_contract = local_probe("C01", "capacity-2")
    broken = "\n".join(
        line for line in raw.splitlines()
        if not any(marker in line for marker in (
            "starts performing", "subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> completed",
            "frees resources", "<AIR-TYPE,0> preparation ended",
        ))
    )
    result = RESOURCES.validate_resource_behavior("C01", "capacity-2", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "two_person_lease")["passed"]


def test_c01_blocked_variant_rejects_injected_work_start():
    raw, report_doc, case_contract = local_probe("C01", "capacity-1")
    broken = raw + "\nTime: 7.6 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> starts performing, planned to last for 0.5 hours\n"
    result = RESOURCES.validate_resource_behavior("C01", "capacity-1", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "no_partial_lease_or_launch")["passed"]


def test_c02_blocked_service_rejects_injected_equipment_lease():
    raw, report_doc, case_contract = local_probe("C02", "equipment-zero")
    broken = raw + "\nTime: 7.8 <E-GSE at <BASE-01,0>> allocated to maintenance task: 1 available now: 0\n"
    result = RESOURCES.validate_resource_behavior("C02", "equipment-zero", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "no_partial_service_lease")["passed"]


def test_c03_grant_before_request_and_booking_is_rejected():
    raw, report_doc, case_contract = local_probe("C03", "staffing-1")
    grant = "Time: 7.5  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0"
    broken = grant + "\n" + raw.replace(grant + "\n", "", 1)
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "first_owner_ledger")["passed"]


def test_c03_received_after_perform_is_rejected():
    raw, report_doc, case_contract = local_probe("C03", "staffing-1")
    received = "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> resource received"
    performing = "Time: 8  subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> starts performing, planned to last for 0.5 hours"
    broken = raw.replace(received + "\n", "", 1).replace(performing, performing + "\n" + received, 1)
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "second_owner_wait_regrant_ledger")["passed"]


def test_c03_zero_rejects_injected_booking():
    raw, report_doc, case_contract = local_probe("C03", "staffing-0")
    broken = raw + "\nTime: 7.6 subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> books resources\n"
    result = RESOURCES.validate_resource_behavior("C03", "staffing-0", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "both_owners_blocked_without_grant")["passed"]


def test_c02_blocked_service_rejects_injected_perform():
    raw, report_doc, case_contract = local_probe("C02", "equipment-zero")
    broken = raw + "\nTime: 7.8 subtask 1 seqno 2 within system preparation task 0 on <AIR-TYPE,0> starts performing, planned to last for 0.333333 hours\n"
    result = RESOURCES.validate_resource_behavior("C02", "equipment-zero", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "no_partial_service_lease")["passed"]


def test_duplicate_availability_detail_is_rejected():
    raw, report_doc, case_contract = local_probe("C01", "capacity-2")
    detail = "  Availability test on  <P-CREW at <BASE-01,0>> request for: 2 OK "
    broken = raw.replace(detail, detail + "\n" + detail, 1)
    result = RESOURCES.validate_resource_behavior("C01", "capacity-2", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "qualified_request_identity_and_quantity")["passed"]


def test_duplicate_request_is_rejected():
    raw, report_doc, case_contract = local_probe("C01", "capacity-2")
    request = "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> requests resources"
    broken = raw.replace(request, request + "\n" + request, 1)
    result = RESOURCES.validate_resource_behavior("C01", "capacity-2", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "two_person_lease")["passed"]


def test_launch_before_preparation_end_is_rejected():
    raw, report_doc, case_contract = local_probe("C01", "capacity-2")
    launch = "Time: 8 <MISSION-BASIC,RESOURCE-UNIT,0,0,0> mission starting, duration: 1 : <AIR-TYPE,0>"
    prep = "Time: 8 <AIR-TYPE,0> preparation ended, mission: <MISSION-BASIC,RESOURCE-UNIT,0,0,0>"
    broken = raw.replace(launch + "\n", "", 1).replace(prep, launch + "\n" + prep, 1)
    result = RESOURCES.validate_resource_behavior("C01", "capacity-2", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "mission_launch_and_completion")["passed"]


def test_c01_blocked_rejects_resource_received_and_free_events():
    raw, report_doc, case_contract = local_probe("C01", "capacity-1")
    broken = raw.replace(
        "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> resource availability test",
        "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> resource availability test\n"
        "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> resource received\n"
        "Time: 7.5  subtask 0 seqno 1 within system preparation task 0 on <AIR-TYPE,0> frees resources",
        1,
    )
    result = RESOURCES.validate_resource_behavior("C01", "capacity-1", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "no_partial_lease_or_launch")["passed"]


def test_c02_inspect_release_must_precede_service_request():
    raw, report_doc, case_contract = local_probe("C02", "both-available")
    release = "Time: 7.66667  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1"
    request = "Time: 7.66667  subtask 1 seqno 2 within system preparation task 0 on <AIR-TYPE,0> requests resources"
    broken = raw.replace(release + "\n", "", 1).replace(request, request + "\n" + release, 1)
    result = RESOURCES.validate_resource_behavior("C02", "both-available", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "inspect_release_precedes_service_request")["passed"]


def test_c03_first_release_must_precede_waiting_owner_retry():
    raw, report_doc, case_contract = local_probe("C03", "staffing-1")
    release = "Time: 8  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1"
    retry = ("Time: 8  subtask 1 seqno 1 within system preparation task 1 on <AIR-TYPE,1> resource availability test\n"
             "  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK ")
    broken = raw.replace(release + "\n", "", 1).replace(retry, retry + "\n" + release, 1)
    result = RESOURCES.validate_resource_behavior("C03", "staffing-1", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "second_owner_wait_regrant_ledger")["passed"]


def test_decreasing_native_timestamp_is_rejected():
    raw, report_doc, case_contract = local_probe("C01", "capacity-2")
    broken = raw + "\nTime: 7.0 injected earlier timestamp\n"
    result = RESOURCES.validate_resource_behavior("C01", "capacity-2", broken, report_doc, case_contract)
    assert not result["passed"]
    assert not next(item for item in result["assertions"] if item["id"] == "nondecreasing_native_timestamps")["passed"]


def test_zero_capacity_is_explicitly_unsupported_without_successful_native_run():
    result = RESOURCES.validate_resource_behavior("C03", "unsupported", "", {}, CONTRACT)
    assert not result["passed"]
    assert result["status"] == "unsupported_pending_native_evidence"
