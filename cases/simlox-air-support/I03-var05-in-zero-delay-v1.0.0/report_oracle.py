"""Predeclared source/event oracle for all 5,210 report cells per arm."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import struct

from build import typed_equal
from check_roundtrip import parse

HERE = Path(__file__).resolve().parent
DESIGN = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
GATE = DESIGN["report_gate"]
FIELDS = GATE["source_event_expected"]
PARENT_REPORT_ROW = DESIGN["source_lineage"]["accepted_parent"]["raw_report"]
PARENT_REPORT = HERE.parents[2] / PARENT_REPORT_ROW["path"]
TOPOLOGY = GATE["topology_exact"]
SYSTEM_CLASSES = FIELDS["SystemResults"]["field_classes"]
STOCK_CLASSES = FIELDS["StockTotalResults"]["field_classes"]
RESOURCE_CLASSES = FIELDS["ResourceResults"]["field_classes"]


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def exposure(start: float, end: float, left: float, right: float) -> float:
    assert 0 <= start <= end <= 36
    return max(0.0, min(right, end) - max(left, start)) / (right - left)


def field_partition(columns: list[str], groups: list[list[str]]) -> None:
    assigned = [field for group in groups for field in group]
    assert len(assigned) == len(set(assigned)) and set(assigned) == set(columns), (columns, assigned)


field_partition(TOPOLOGY[2]["columns"], list(SYSTEM_CLASSES.values()))
field_partition(TOPOLOGY[3]["columns"], list(STOCK_CLASSES.values()))
field_partition(TOPOLOGY[4]["columns"], list(RESOURCE_CLASSES.values()))
field_partition(TOPOLOGY[5]["columns"], [RESOURCE_CLASSES["identity_and_interval"][:2],
                                        RESOURCE_CLASSES["source_event_dynamic"], RESOURCE_CLASSES["source_event_zero"]])


def expected(timeline: dict, *, parent: bool) -> dict[str, list[dict]]:
    """Only parsed typed events and frozen source constants supply numeric expectations."""
    waves = timeline["waves"]
    assert len(waves) == 2
    assert timeline["out_request"] == 7.75
    assert timeline["out_departure"] == 8
    assert timeline["in_start"] == 10
    assert timeline["in_task_arrival"] == (10.5 if parent else 10)
    assert timeline["in_local_receipt"] == (10.5 if parent else 10)
    assert timeline["opening"] == 2 and timeline["out_quantity"] == timeline["in_quantity"] == 1
    result: dict[str, list[dict]] = {"SystemResults": [], "StockTotalResults": [], "ResourceResults": []}
    for bin_index in range(72):
        left, right = bin_index / 2, (bin_index + 1) / 2
        assigned = sum(2 * exposure(w["prep_start"], w["return"], left, right) for w in waves)
        mission = sum(2 * exposure(w["mission_start"], w["return"], left, right) for w in waves)
        preparation = sum(2 * exposure(w["prep_start"], w["prep_end"], left, right) for w in waves)
        prepared_wait = sum(2 * exposure(w["prep_end"], w["mission_start"], left, right) for w in waves)
        starts = sum(2 for w in waves if left <= w["prep_start"] < right)
        completions = sum(2 for w in waves if left <= w["prep_end"] < right)
        system = {field: 0 for field in SYSTEM_CLASSES["source_event_zero"] +
                  SYSTEM_CLASSES["bounded_native_presentation_zero"]}
        system.update(UNID="Total over all Units", SID="Total over all Systems", STINT=left, ETINT=right,
                      NSYRY=2-assigned, NSYMA=assigned, NSYMO=mission, NSYMP=preparation,
                      NSYMR=prepared_wait, NSYA=2, FTMO=mission/2, STACC=mission,
                      NPSTA=starts, NPSUC=completions, SYDT=None)
        assert set(system) == set(TOPOLOGY[2]["columns"])
        result["SystemResults"].append(system)
        stock = {field: 0 for field in STOCK_CLASSES["exact_zero"]}
        stock.update(STINT=left, ETINT=right, PNB=1,
                     NBOU=None, ROS=None, ROST=None, WT=None, WTT=None, WTS=None)
        assert set(stock) == set(TOPOLOGY[3]["columns"])
        result["StockTotalResults"].append(stock)
        out_fraction = exposure(timeline["out_departure"], 36, left, right)
        in_fraction = exposure(timeline["in_local_receipt"], 36, left, right)
        nominal_out = exposure(timeline["out_request"], 36, left, right)
        local = 2 - out_fraction + in_fraction
        nominal = 2 - nominal_out + in_fraction
        booked = sum(2 * exposure(w["prep_start"], w["prep_end"], left, right) for w in waves)
        resource = {field: 0 for field in RESOURCE_CLASSES["source_event_zero"]}
        resource.update(RID="Total over all Resources", STID="Total over all Stations", STINT=left, ETINT=right,
                        NR=local, NRA=local, NRN=nominal, NRUM=booked, NRW=0)
        assert set(resource) == set(TOPOLOGY[4]["columns"])
        result["ResourceResults"].append(resource)
    total = {field: 0 for field in RESOURCE_CLASSES["source_event_zero"]}
    integrals = {field: sum(row[field]/2 for row in result["ResourceResults"])
                 for field in RESOURCE_CLASSES["source_event_dynamic"]}
    for field in integrals:
        total[field] = f32(integrals[field] / 36)
    total.update(RID="Total over all Resources", STID="Total over all Stations")
    assert set(total) == set(TOPOLOGY[5]["columns"])
    expected_hours = {"NR": 69.5 if parent else 70, "NRA": 69.5 if parent else 70,
                      "NRN": 69.25 if parent else 69.75, "NRUM": 2, "NRW": 0}
    assert integrals == expected_hours, integrals
    if not parent:
        assert {field: total[field] for field in FIELDS["ResourceResultsTotal"]["expected_float32"]} == \
               FIELDS["ResourceResultsTotal"]["expected_float32"]
    system_integrals = {field: sum(row[field]/2 for row in result["SystemResults"])
                        for field in FIELDS["SystemResults"]["integrals_halfhour_weighted"]}
    assert system_integrals == FIELDS["SystemResults"]["integrals_halfhour_weighted"]
    assert sum(row["FTMO"] for row in result["SystemResults"]) == 4
    assert sum(row["NPSTA"] for row in result["SystemResults"]) == 4
    assert sum(row["NPSUC"] for row in result["SystemResults"]) == 4
    result["ProblemDescription"] = [{"PDESC": DESIGN["source_delta"]["parent_description"] if parent
                                     else DESIGN["source_delta"]["child_description_predeclared"]}]
    result["ResultSummary"] = [FIELDS["ResultSummary"]]
    result["ResourceResultsTotal"] = [total]
    return result


def check_report(report: dict, timeline: dict, *, parent: bool) -> int:
    rows_expected = expected(timeline, parent=parent)
    assert PARENT_REPORT.is_file() and PARENT_REPORT.stat().st_size == PARENT_REPORT_ROW["bytes"]
    assert hashlib.sha256(PARENT_REPORT.read_bytes()).hexdigest() == PARENT_REPORT_ROW["sha256"]
    parent_tables = parse(PARENT_REPORT)["report"]["tables"]
    assert set(report) == {"report"} and set(report["report"]) == {"tables"}
    tables = report["report"]["tables"]
    assert [table["name"] for table in tables] == GATE["six_tables_in_order"]
    count = 0
    for table, spec, parent_table in zip(tables, TOPOLOGY, parent_tables):
        name = spec["name"]
        assert set(table) == {"name", "columns", "instances"}
        assert len(table["columns"]) == len(spec["columns"])
        assert [column["name"] for column in table["columns"]] == spec["columns"]
        assert typed_equal(table["columns"], parent_table["columns"]), (name, "column metadata")
        for column in table["columns"]:
            assert set(column) in ({"name", "datatype"}, {"name", "datatype", "key"})
            assert type(column["datatype"]) is str
            if "key" in column:
                assert type(column["key"]) is bool
        assert len(table["instances"]) == 1
        instance = table["instances"][0]
        assert set(instance) == {"instance_name", "rows"}
        assert instance["instance_name"] == spec["instance_name"]
        assert len(instance["rows"]) == spec["rows"]
        for index, (row, wanted) in enumerate(zip(instance["rows"], rows_expected[name])):
            assert len(row) == len(spec["columns"])
            for field, actual in zip(spec["columns"], row):
                value = wanted[field]
                if name == "ResultSummary" and field == "NREP":
                    assert type(actual) is int and actual == value, (name, index, field, actual, value)
                elif type(value) in (int, float):
                    assert type(actual) in (int, float) and math.isfinite(actual) and actual == value, (name, index, field, actual, value)
                else:
                    assert type(actual) is type(value) and actual == value, (name, index, field, actual, value)
                count += 1
    assert count == 5210
    return count
