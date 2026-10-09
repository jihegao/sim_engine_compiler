"""Full 4,044-cell frozen prospective report predicate evaluation."""
from __future__ import annotations

import hashlib
from pathlib import Path

from event_ledger import semantic, oracle
from model_common import HERE, PATTERN_PIN, REPORT_RULES_PIN, exact, strict_json

def compare(raw: bytes, ledger: dict) -> dict[str, object]:
    catalog = strict_json(exact(HERE / "preserved-oracle/report-predicates.json", REPORT_RULES_PIN))
    assert catalog["schema"] == "i05-var04-report-predicates/v101"
    assert catalog["cell_count"] == 4044
    cells = oracle.compare_report(raw, catalog, ledger)
    assert cells == 4044
    return {"schema":"i05-var04-complete-report/v103", "passed":True,
            "tables":4, "rows":146, "typed_cells":cells,
            "native_calls":0, "raw_sha256":hashlib.sha256(raw).hexdigest()}

def compare_file(path: Path, ledger: dict) -> dict[str, object]:
    return compare(path.read_bytes(), ledger)
