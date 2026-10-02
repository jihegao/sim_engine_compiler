"""Append bounded warning-bearing I01.var05 restricted diagnostic."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var05.none_maintenance_repair_suppression_restricted.1.0.0",
    "case_id": "I01", "variant_id": "I01.var05", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "RESTRICTED WARNING-BEARING DIAGNOSTIC, not full I01.var05 acceptance: accepted I01.var01 parent with task-referenced LRU-CM/BASE ItemRepair, matching AIR_BASIC MaintenanceAllocation at BASE-01 versus AIR_NONE at <NONE>, both stock POINTs STSIZ1 and only Control.APID/description different between arms; both converter errors0, 23-table exact roundtrip, shared h9.8829 LRU failure/abort, h10 spare issue and h10.5 system ready, later missions succeed; matching item DIRP h10.1667-11.1667 returns failed LRU ID1 to stock level1, <NONE> arm has no DIRP/stock return/reorder and local stock remains level0, run.log warning241 incomplete item repair, final failed-item disposition unresolved; 72 System/Stock bins per arm agree on aircraft metrics but cannot prove physical item conservation; two guarded SSH runs, 24 sealed local raw artifacts, author23/23 and independent1971/1971 restricted GO; no complete reorder, discard, generic <NONE>, task category/level/station filtering, GUI visual or cross-engine acceptance; earlier missing-category converter error2038 remains unpublished"
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
        "I01.var02.stock_only_blank_APID_no_stock.1.0.0")
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
