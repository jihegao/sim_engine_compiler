"""Prospective full 4,966-cell J07-selected report equality, with one STOTD change."""

from __future__ import annotations

import copy
from pathlib import Path

from model_common import HERE, J07_CONTROL_SHA, compare_tables, compare_typed, read_native_report, seal, strict_json

CONTROL = HERE.parent / "J07-unit-type-report-v1.0.0/runs/report-settings/a17-group-report-20261001-01/report-raw.json"
CONTROL_BYTES = 146793
TABLES = ["ProblemDescription", "ResultSummary", "MissionResults", "MissionResultsTotal",
          "FixedMissionResults", "FixedMissionResultsTotal", "SystemResults", "StockTotalResults"]
COLS = [1, 11, 12, 10, 25, 23, 40, 16]
ROWS = [1, 1, 72, 1, 1, 1, 72, 72]


def expected_report() -> dict:
    body = CONTROL.read_bytes()
    assert len(body) == CONTROL_BYTES and seal(CONTROL)["sha256"] == J07_CONTROL_SHA
    control = strict_json(body)
    assert type(control) is dict and set(control) == {"report"}
    expected = copy.deepcopy(control)
    report = expected["report"]
    assert type(report) is dict and set(report) == {"database_version", "tables"}
    tables = report["tables"]
    assert [t["name"] for t in tables] == TABLES
    assert [len(t["columns"]) for t in tables] == COLS
    assert [sum(len(i["rows"]) for i in t["instances"]) for t in tables] == ROWS
    fixed = tables[4]
    assert len(fixed["instances"]) == 1 and fixed["instances"][0]["instance_name"] == ""
    assert len(fixed["instances"][0]["rows"]) == 1
    assert fixed["columns"][22] == {"datatype": "double", "name": "STOTD"}
    row = fixed["instances"][0]["rows"][0]
    assert row[0:2] == ["TEACH-GROUP", "Total over all Missions"] and type(row[22]) is int and row[22] == 0
    row[22] = 1
    return expected


def compare(raw: bytes) -> dict:
    expected = expected_report()
    actual = read_native_report(raw)
    assert type(actual) is dict and set(actual) == {"report"}
    assert type(actual["report"]) is dict and set(actual["report"]) == {"database_version", "tables"}
    assert compare_typed(expected["report"]["database_version"], actual["report"]["database_version"])
    tables = actual["report"]["tables"]
    assert [t["name"] for t in tables] == TABLES
    assert [len(t["columns"]) for t in tables] == COLS
    assert [sum(len(i["rows"]) for i in t["instances"]) for t in tables] == ROWS
    assert compare_tables(expected["report"]["tables"], tables) == 4966
    return {"schema": "a17-var06-complete-report/v100", "passed": True,
            "tables": 8, "rows": 221, "typed_cells": 4966, "single_changed_cell": "FixedMissionResults.STOTD",
            "stotd": 1, "native_calls": 0}


def compare_file(path: Path) -> dict:
    result = compare(path.read_bytes())
    result["raw_sha256"] = seal(path)["sha256"]
    return result


if __name__ == "__main__":
    raise SystemExit("Use compare_file(path) from the source-bound child checker")
