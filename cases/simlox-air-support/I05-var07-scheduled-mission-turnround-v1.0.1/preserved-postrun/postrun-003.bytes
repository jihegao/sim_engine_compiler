"""Read-only package source and prospective oracle audit; no regeneration."""
from __future__ import annotations

import json

from check_roundtrip import source_oracles
from model_common import HERE, LOG_PIN, REPORT_PIN, exact, strict_json, count_model
from source_gate import verify as verify_source

def verify() -> dict[str, object]:
    source = verify_source()
    models = source_oracles()
    log=exact(HERE/"preserved-design/expected-model.log",LOG_PIN)
    assert log.count(b"\r\n")==log.count(b"\n")==115
    report=strict_json(exact(HERE/"preserved-design/expected-report.json",REPORT_PIN))
    assert count_model(report,"report")=={"tables":4,"rows":146,"cells":4044}
    return {"schema":"i05-var07-readonly-build/v101", "passed":True,
            "source":source, "model_counts":{"authored":count_model(models["authored"],"model"),
                                        "exported":count_model(models["exported"],"model")},
            "physical_log_lines":115, "timed_log_lines":107,
            "report_typed_cells":4044,
            "native_calls":0, "accepted_checker_calls":0}

if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
