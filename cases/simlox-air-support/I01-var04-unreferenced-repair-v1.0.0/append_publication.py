"""Append the bounded I01.var04 unreferenced-repair publication entry."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var04.unreferenced_item_repair_under_NONE.1.0.0",
    "case_id": "I01", "variant_id": "I01.var04", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded one-LRU no-task-reference ItemRepair activation: accepted I01.var01 stock foundation and restricted I01.var05 AIR_NONE source; byte-identical referenced control versus child clearing only ItemRepair.DIRPTID plus description, APID AIR_NONE and MaintenanceAllocation LRU-CM/BASE/<NONE> fixed; both zero converter errors and exact 23-table roundtrips, same h9.8829 LRU failure/first mission abort, h10 spare issue, h10.5 aircraft ready and two later mission successes; referenced failed LRU ID1 arrives h10.1667 without DIRP/stock return and warning241 incomplete repair, unreferenced ID1 DIRP h10.1667-11.1667 returns to local stock level1 with no warning241; 72-bin System/Stock reports and business summary equal, so individual events/stock ledger establish item path; two guarded SSH runs, 24 sealed local raw artifacts, author23/23 and independent1974/1974 bounded GO; no ItemReorder path, full <NONE> procurement, referenced-arm item conservation, general unreferenced allocation, category/level/station filtering, StationVariant, GUI visual or cross-engine claim"
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
        "I01.var05.none_maintenance_repair_suppression_restricted.1.0.0")
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
