"""Complete 4,044-cell typed report comparison for the bounded child."""

from __future__ import annotations

import json
from pathlib import Path

from model_common import HERE, REPORT_SHA, compare_tables, read_native_report, read_pinned_json, seal


def compare(raw: bytes) -> dict:
    expected = read_pinned_json(HERE / "prospective-report-oracle.json", REPORT_SHA)
    assert expected["schema"] == "a17-var01-prospective-derived-report/v1"
    assert expected["cell_count"] == 4044
    actual = read_native_report(raw)
    assert type(actual) is dict and set(actual) == {"report"}
    assert type(actual["report"]) is dict and set(actual["report"]) == {"tables"}
    tables = actual["report"]["tables"]
    assert [x["name"] for x in tables] == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"]
    assert [len(x["instances"][0]["rows"]) for x in tables] == [1, 1, 72, 72]
    assert [len(x["columns"]) for x in tables] == [1, 11, 40, 16]
    assert compare_tables(expected["tables"], tables) == 4044
    return {"schema": "a17-var01-complete-report/v1", "passed": True,
            "tables": 4, "rows": 146, "typed_cells": 4044, "native_calls": 0}


def compare_file(path: Path) -> dict:
    result = compare(path.read_bytes())
    result["raw_sha256"] = seal(path)["sha256"]
    return result


if __name__ == "__main__":
    raise SystemExit("Use compare_file(path) from the source-bound child checker")
