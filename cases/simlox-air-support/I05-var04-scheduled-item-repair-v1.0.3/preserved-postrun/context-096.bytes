"""Read-only package source and prospective oracle audit; no regeneration."""
from __future__ import annotations

import json

from check_roundtrip import source_oracles
from model_common import HERE, PATTERN_PIN, REPORT_RULES_PIN, exact, strict_json
from source_gate import verify as verify_source

def verify() -> dict[str, object]:
    source = verify_source()
    models = source_oracles()
    patterns = strict_json(exact(HERE / "preserved-oracle/log-patterns.json", PATTERN_PIN))
    assert patterns["schema"] == "i05-var04-log-patterns/v101"
    assert patterns["physical_lines"] == 222 and patterns["timed_lines"] == 186 and len(patterns["lines"]) == 222
    report = strict_json(exact(HERE / "preserved-oracle/report-predicates.json", REPORT_RULES_PIN))
    assert report["schema"] == "i05-var04-report-predicates/v101"
    assert report["cell_count"] == len(report["predicates"]) == 4044
    return {"schema":"i05-var04-readonly-build/v103", "passed":True,
            "source":source, "model_counts":models["counts"],
            "physical_log_lines":222, "timed_log_lines":186,
            "report_typed_cells":4044,
            "native_calls":0, "accepted_checker_calls":0}

if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
