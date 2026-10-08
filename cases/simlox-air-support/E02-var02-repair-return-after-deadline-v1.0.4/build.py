"""Read-only package and prospective source audit. Never regenerates an oracle."""

from __future__ import annotations

import json

from check_roundtrip import source_oracles
from model_common import HERE, PATTERN_PIN, REPORT_PIN, count_model, exact, strict_json
from source_gate import verify as verify_source


def verify() -> dict[str, object]:
    source = verify_source(require_absent_native=False)
    models = source_oracles()
    patterns = strict_json(exact(HERE / "preserved-oracle/log-patterns.json", PATTERN_PIN))
    assert patterns["schema"] == "e02-var02-prospective-full-log-patterns/v104"
    assert patterns["physical_lines"] == 123 and patterns["timed_lines"] == 99
    assert len(patterns["lines"]) == 123
    expected = strict_json(exact(HERE / "preserved-oracle/expected-report.json", REPORT_PIN))
    assert count_model(expected, "report") == {"tables": 4, "rows": 146, "cells": 4044}
    return {"schema": "e02-var02-readonly-build/v104", "passed": True,
            "source": source, "model": models, "physical_log_lines": 123,
            "timed_log_lines": 99, "report_cells": 4044,
            "native_calls": 0, "accepted_checker_calls": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
