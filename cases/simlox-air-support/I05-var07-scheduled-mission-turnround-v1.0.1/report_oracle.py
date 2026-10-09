"""Strict full typed report comparator for the frozen one-rep prospective arm."""
from __future__ import annotations

import hashlib
from pathlib import Path

from model_common import HERE, REPORT_PIN, exact, strict_json, native_report_json, compare_tables, typed_equal

def compare(raw: bytes, ledger: dict) -> dict[str,object]:
    assert ledger["physical_lines"]==115 and ledger["timed_lines"]==107
    expected=strict_json(exact(HERE/"preserved-design/expected-report.json",REPORT_PIN))
    actual=native_report_json(raw)
    assert type(expected) is type(actual) is dict and set(expected)==set(actual)=={"report"}
    assert type(expected["report"]) is type(actual["report"]) is dict
    assert set(expected["report"])==set(actual["report"])=={"tables"}
    assert compare_tables(expected["report"]["tables"],actual["report"]["tables"])==4044
    assert typed_equal(expected,actual), "native report representation differs"
    return {"schema":"i05-var07-complete-report/v101","passed":True,"tables":4,
            "rows":146,"typed_cells":4044,"native_calls":0,
            "raw_sha256":hashlib.sha256(raw).hexdigest()}

def compare_file(path: Path, ledger: dict) -> dict[str,object]:
    return compare(path.read_bytes(),ledger)
