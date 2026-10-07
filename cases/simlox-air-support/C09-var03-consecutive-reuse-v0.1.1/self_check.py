"""In-memory and temporary-copy mutation probes; never writes accepted raw."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from native_json import read
from report_oracle import FIELDS, cell_equal, check_report

HERE = Path(__file__).resolve().parent
REMOTE = HERE.parent / "C09-var04-remote-maintenance-resource-v1.0.0/runs/c09-var04-remote-20261002-01"


def main():
    assert not cell_equal(1e-9, 0, "SystemResults", "NPMT"), "subepsilon count mutation accepted"
    assert not cell_equal(1e-9, 0, "ResourceResults", "NRUM"), "full-bin zero mutation accepted"
    assert not cell_equal(None, 0, "StockTotalResults", "NBO"), "null mutation accepted"
    assert not cell_equal(True, 1, "ResultSummary", "NREP"), "boolean count mutation accepted"
    assert cell_equal(2.4352, 2.4351303577, "ResourceResults", "NR"), "printed-time bound too narrow"
    assert not cell_equal(2.436, 2.4351303577, "ResourceResults", "NR"), "printed-time bound too wide"
    original = read(REMOTE / "report-raw.json")
    tables = {table["name"]: table for table in original["report"]["tables"]}
    cells, issues = check_report("remote", REMOTE / "input.json", REMOTE / "model.log", REMOTE / "report-raw.json")
    assert cells == 5210 and not issues
    with tempfile.TemporaryDirectory() as name:
        target = Path(name) / "mutated.json"
        probes = [
            ("SystemResults", 25, "NPMT", 1e-9),
            ("SystemResults", 25, "NSYRP", 0.37),
            ("SystemResults", 25, "SYDT", 2.0),
            ("StockTotalResults", 25, "NBO", 1),
            ("StockTotalResults", 25, "NBOU", 0),
            ("ResourceResults", 19, "NRW", 0.17),
            ("ResourceResults", 19, "RID", "other resource"),
            ("ResourceResultsTotal", 0, "NRUM", 7),
            ("ResultSummary", 0, "MTMF", 0.9),
        ]
        for table_name, row, field, value in probes:
            table = tables[table_name]
            cell = FIELDS[table_name].index(field)
            old = table["instances"][0]["rows"][row][cell]
            table["instances"][0]["rows"][row][cell] = value
            target.write_text(json.dumps(original), encoding="utf-8")
            _, found = check_report("remote", REMOTE / "input.json", REMOTE / "model.log", target)
            assert found, (table_name, row, field, value)
            table["instances"][0]["rows"][row][cell] = old
    return {"decision": "PASS", "negative_mutations_rejected": len(probes),
            "scalar_probes": 6, "baseline_cells": cells}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
