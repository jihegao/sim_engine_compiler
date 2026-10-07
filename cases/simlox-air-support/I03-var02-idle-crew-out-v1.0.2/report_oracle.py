"""Predeclared source/event oracle for all 5,210 child report cells."""
from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
import struct

from build import typed_equal
from check_roundtrip import parse

HERE = Path(__file__).resolve().parent
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
GATE = CONTRACT["report_gate"]
PARENT_REPORT = HERE.parent / "I03-var01-crew-out-in-v1.0.0" / "runs" / "i03-var01-crew-transfer-v100-ssh-20261005-01" / "out-report-raw.json"
PARENT_REPORT_SHA = "eb921d0b07b33528f56ee2cf1e7e69270d92a1f95f79702652b419ec9700c433"
DESCRIPTION = CONTRACT["source_delta"]["allowed_changes_exactly"][0]["to"]
SYSTEM = GATE["topology"][2]["columns"]
STOCK = GATE["topology"][3]["columns"]
RESOURCE = GATE["topology"][4]["columns"]
TOTAL = GATE["topology"][5]["columns"]


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def exposure(start: float, end: float, left: float, right: float) -> float:
    assert 0 <= start <= end <= 36
    return max(0.0, min(right, end) - max(left, start)) / (right - left)


def expected(timeline: dict) -> dict[str, list[dict]]:
    """Use only the separately validated source/event timeline, never report cells."""
    waves = timeline["waves"]
    assert len(waves) == 2 and timeline["out_departure"] == timeline["out_arrival"] == 6
    assert timeline["transfer_quantity"] == 1
    system, stock, resource = [], [], []
    for i in range(72):
        left, right = i / 2, (i + 1) / 2
        assigned = sum(2 * exposure(w["preparation_start"], w["return"], left, right) for w in waves)
        work_wait = sum(2 * exposure(w["preparation_start"], w["first_preparation_end"], left, right)
                        + exposure(w["first_preparation_end"], w["last_preparation_end"], left, right) for w in waves)
        prepared = sum(exposure(w["first_preparation_end"], w["last_preparation_end"], left, right) for w in waves)
        mission = sum(2 * exposure(w["launch"], w["return"], left, right) for w in waves)
        starts = sum(2 for w in waves if left <= w["preparation_start"] < right)
        completions = sum(int(left <= w["first_preparation_end"] < right) + int(left <= w["last_preparation_end"] < right) for w in waves)
        s = {name: 0 for name in SYSTEM}
        s.update(UNID="Total over all Units", SID="Total over all Systems", STINT=left, ETINT=right,
                 NSYRY=2-assigned, NSYMA=assigned, NSYMO=mission, NSYMP=work_wait,
                 NSYMR=prepared, NSYA=2, FTMO=mission/2, STACC=mission,
                 SYDT=None, NPSTA=starts, NPSUC=completions)
        system.append(s)
        t = {name: 0 for name in STOCK}
        t.update(STINT=left, ETINT=right, PNB=1,
                 NBOU=None, ROS=None, ROST=None, WT=None, WTT=None, WTS=None)
        stock.append(t)
        cap = 2 if right <= timeline["out_departure"] else 1
        booking = sum(exposure(a, b, left, right) for w in waves for a, b in w["bookings"])
        waiting = sum(exposure(a, b, left, right) for w in waves for a, b in w["waits"])
        r = {name: 0 for name in RESOURCE}
        r.update(RID="Total over all Resources", STID="Total over all Stations",
                 STINT=left, ETINT=right, NR=cap, NRA=cap, NRN=cap, NRUM=booking, NRW=waiting)
        resource.append(r)
    totals = {name: 0 for name in TOTAL}
    total_resource_hours = sum((row["NR"] / 2) for row in resource)
    total_booking_hours = sum((row["NRUM"] / 2) for row in resource)
    total_wait_hours = sum((row["NRW"] / 2) for row in resource)
    totals.update(RID="Total over all Resources", STID="Total over all Stations",
                  NR=f32(total_resource_hours/36), NRA=f32(total_resource_hours/36),
                  NRN=f32(total_resource_hours/36), NRUM=f32(total_booking_hours/36),
                  NRW=f32(total_wait_hours/36))
    assert total_resource_hours == 42 and total_booking_hours == 2 and total_wait_hours == 1
    assert {k: totals[k] for k in GATE["resource_fields"]["total_expected_float32"]} == GATE["resource_fields"]["total_expected_float32"]
    integrals = {field: sum(row[field]/2 for row in system) for field in GATE["source_event_integrals_aircraft_hours"]}
    assert integrals == GATE["source_event_integrals_aircraft_hours"], integrals
    assert sum(row["NPSTA"] for row in system) == sum(row["NPSUC"] for row in system) == 4
    return {"ProblemDescription": [{"PDESC": DESCRIPTION}],
            "ResultSummary": [GATE["result_summary_expected"]],
            "SystemResults": system, "StockTotalResults": stock,
            "ResourceResults": resource, "ResourceResultsTotal": [totals]}


def check_report(report: dict, timeline: dict) -> int:
    expected_rows = expected(timeline)
    assert hashlib.sha256(PARENT_REPORT.read_bytes()).hexdigest() == PARENT_REPORT_SHA
    parent_tables = parse(PARENT_REPORT)["report"]["tables"]
    assert set(report) == {"report"} and set(report["report"]) == {"tables"}
    tables = report["report"]["tables"]
    assert [table["name"] for table in tables] == GATE["tables_in_order"]
    comparisons = 0
    for table, spec in zip(tables, GATE["topology"]):
        name = spec["name"]
        assert set(table) == {"name", "columns", "instances"}, name
        assert len(table["columns"]) == len(spec["columns"])
        assert [c["name"] for c in table["columns"]] == spec["columns"]
        assert typed_equal(table["columns"], parent_tables[GATE["tables_in_order"].index(name)]["columns"]), (name, "column metadata")
        assert len({c["name"] for c in table["columns"]}) == len(spec["columns"])
        # Native report metadata is part of the gate, including column datatype and key presence.
        for col in table["columns"]:
            assert set(col) == {"name", "datatype"} or set(col) == {"name", "datatype", "key"}, (name, col)
            assert type(col["datatype"]) is str
            if "key" in col:
                assert type(col["key"]) is bool
        assert len(table["instances"]) == 1
        inst = table["instances"][0]
        assert set(inst) == {"instance_name", "rows"}
        assert inst["instance_name"] == spec["instance_name"]
        rows = inst["rows"]
        assert len(rows) == spec["rows"]
        for i, (row, wanted) in enumerate(zip(rows, expected_rows[name])):
            assert len(row) == len(spec["columns"])
            for field, actual in zip(spec["columns"], row):
                value = wanted[field]
                if type(value) in (int, float):
                    assert type(actual) in (int, float) and math.isfinite(actual) and actual == value, (name, i, field, actual, value)
                else:
                    assert type(actual) is type(value) and actual == value, (name, i, field, actual, value)
                comparisons += 1
    assert comparisons == 5210
    return comparisons
