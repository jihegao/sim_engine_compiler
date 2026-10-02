"""Append bounded I01.var01 stock-only APID POINT publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var01.stock_only_two_POINT_APID_selection.1.0.0",
    "case_id": "I01", "variant_id": "I01.var01", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted E01 local-spare explicit-replacement parent; shared two StockAllocation rows AIR_BASIC STSIZ1 and AIR_EMPTY STSIZ0, stocked APID AIR_BASIC versus empty APID AIR_EMPTY with only Control.APID and description different; both have same h9.8829 critical mounted-LRU failure and first mission abort, stocked local spare taken h10 and system replacement/ready h10.5, empty local backorder h10, failed LRU repaired and reused h11.1667, replacement/ready h11.5; later missions succeed, 72 System/Stock bins reconcile one ordinary failure, 0.5 system-repair hours and terminal ready1 in both, empty 1.0 item-wait and 1.16667 backorder-hours versus stocked zero; two guarded session0 SSH runs, exact 20-table roundtrips, converter errors0, 24 sealed raw artifacts, author30/30 and independent7604/7604 GO; stock-only POINT at one station/seed, no ResourceAllocation or MaintenanceAllocation selection, APID blank, task category/level, STID NONE, StationVariant, procurement, GUI visual or cross-engine claim"
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
        "H03.var04.subsequent_missions_after_attrition.1.0.0")
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
