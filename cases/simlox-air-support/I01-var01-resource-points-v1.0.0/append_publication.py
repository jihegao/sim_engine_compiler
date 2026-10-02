"""Append the bounded I01.var01 resource-only APID publication entry."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var01.resource_only_two_POINT_APID_selection.1.0.0",
    "case_id": "I01", "variant_id": "I01.var01", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "resource-only POINT/APID selection on accepted C01 v1.0.2 two-P-CREW preparation demand: one model has AIR_BASIC P-CREW2/P-OTHER0 and AIR_ZERO P-CREW0/P-OTHER0 ResourceAllocation rows at BASE-01; paired arms differ only Control.APID and description, no authored stock/maintenance allocation rows; AIR_BASIC leases two crew h7-7.16667, preparation completes h7.5 and mission succeeds h8-10, ResourceResults h7 bin NRUM2/3 (20 person-minutes); AIR_ZERO fails the two-crew request, books no crew, performs no positive work, mission cancels h7.58333, ResourceResults h7 NR0/NRUM0/NRW2, both terminal aircraft ready1; two serial guarded session0 SSH runs, converter errors0 with expected warnings108/126, exact 20 row-containing table roundtrips (17 substantive plus three null placeholders), 72 Resource/System/Stock bins per run, 24 sealed raw files, author24/24 and independent9607/9607 bounded GO; combined StockAllocation/MaintenanceAllocation selection, E01 LRU replacement resources, station routing, StationVariant, GUI visual and cross-engine behavior remain unverified"
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
        "I01.var04.unreferenced_item_repair_under_NONE.1.0.0")
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
