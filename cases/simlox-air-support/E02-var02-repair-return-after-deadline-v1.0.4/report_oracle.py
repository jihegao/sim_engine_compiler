"""Strict full 4,044-cell prospective E02 report comparison."""

from __future__ import annotations

from pathlib import Path

from model_common import HERE, REPORT_PIN, compare_tables, count_model, exact, native_report_json, seal, strict_json


def compare(raw: bytes) -> dict[str, object]:
    expected = strict_json(exact(HERE / "preserved-oracle/expected-report.json", REPORT_PIN))
    actual = native_report_json(raw)
    assert count_model(expected, "report") == count_model(actual, "report") == {
        "tables": 4, "rows": 146, "cells": 4044}
    names = [t["name"] for t in actual["report"]["tables"]]
    assert names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    count = compare_tables(expected["report"]["tables"], actual["report"]["tables"], tolerance=1e-5)
    assert count == 4044
    return {"schema": "e02-var02-complete-report/v104", "passed": True,
            "tables": 4, "rows": 146, "typed_cells": count,
            "numeric_tolerance": 1e-5, "native_calls": 0}


def compare_file(path: Path) -> dict[str, object]:
    result = compare(path.read_bytes())
    result["raw_sha256"] = seal(path)["sha256"]
    return result
