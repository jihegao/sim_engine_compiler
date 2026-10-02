"""Append bounded I01.var02 stock-only blank APID publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var02.stock_only_blank_APID_no_stock.1.0.0",
    "case_id": "I01", "variant_id": "I01.var02", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted I01.var01 AIR_BASIC stocked source is byte-identical selected control with two StockAllocation POINT rows AIR_BASIC STSIZ1 and AIR_EMPTY STSIZ0; child only Control.APID AIR_BASIC to blank/null and description; blank converter notice102 Simulation with no stock and error0, selected log/full report match accepted AIR_BASIC, blank event log and business report ledgers match accepted AIR_EMPTY; shared h9.8829 ordinary critical LRU failure/mission abort, selected spare take h10/ready h10.5 versus blank backorder h10, repaired original reused h11.1667/ready h11.5; later missions succeed, 72 System/Stock bins per arm reconcile one ordinary failure, 0.5 system-repair hours and terminal ready1, blank 1.0 item-wait and 1.16667 backorder-hours versus selected zero; two guarded session0 SSH runs, exact 20-table roundtrips, 24 sealed local raw artifacts, author34/34 and independent7582/7582 GO; stock-only blank APID at one station/seed, no ResourceAllocation or MaintenanceAllocation blank-selection, task category/level, STID NONE, StationVariant, procurement, GUI visual or cross-engine claim"
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    existing = [item for item in doc["entries"] if item["publication_id"] == ENTRY["publication_id"]]
    if existing:
        assert existing == [ENTRY]
        print("entry already present")
        return
    assert doc["entries"][-1]["publication_id"] == (
        "I01.var01.stock_only_two_POINT_APID_selection.1.0.0")
    suffix = "\n  ]\n}\n"
    assert raw.endswith(suffix)
    prefix = raw[:-len(suffix)]
    assert prefix.endswith("}")
    updated = prefix + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + suffix
    parsed = json.loads(updated)
    assert parsed["entries"][-1] == ENTRY and len(parsed["entries"]) == len(doc["entries"]) + 1
    INDEX.write_text(updated, encoding="utf-8", newline="")
    print(ENTRY["publication_id"], len(parsed["entries"]))


if __name__ == "__main__":
    main()
