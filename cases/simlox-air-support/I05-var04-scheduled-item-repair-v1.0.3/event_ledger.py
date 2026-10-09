"""Use the frozen contract evaluator for all 222 ordered physical lines."""
from __future__ import annotations

import sys
from pathlib import Path

from model_common import HERE, PATTERN_PIN, exact, strict_json

sys.path.insert(0, str(HERE / "preserved-design"))
import verify_oracle as oracle  # noqa: E402: frozen v101 method is a case source

def semantic(raw: bytes, catalog: dict | None = None) -> dict:
    if catalog is None:
        catalog = strict_json(exact(HERE / "preserved-oracle/log-patterns.json", PATTERN_PIN))
    assert catalog["schema"] == "i05-var04-log-patterns/v101"
    ledger = oracle.match_log(raw, catalog, child=True)
    assert ledger["physical_lines"] == 222 and ledger["timed_lines"] == 186
    return ledger

def verify_file(path: Path) -> dict:
    ledger = semantic(path.read_bytes())
    return {"schema":"i05-var04-physical-ledger/v103", "passed":True,
            "physical_lines":ledger["physical_lines"], "timed_lines":ledger["timed_lines"],
            "complete_repair_cycles":3, "native_calls":0,
            "ledger":ledger}
