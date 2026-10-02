"""Append bounded I01.var03 joint stock and maintenance selection."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var03.joint_stock_maintenance_APID_matrix.1.0.0",
    "case_id": "I01", "variant_id": "I01.var03", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded four-POINT joint StockAllocation and MaintenanceAllocation APID selection from accepted I01.var03 station parent: BASE-01 initial LRU spare size1 vs2 crossed with BASE vs DEPOT one-hour failed-LRU repair, complete four POINT rows in both tables, all source arms differ only Control.APID and description; four serial guarded SSH runs, converter errors0, exact 24-table roundtrips, 48 local raw seals, author45/45 and independent GO; same first h9.8829 failure, base spare ID0 drawn h10 and aircraft ready h10.5, failed physical LRU ID1 with one spare vs ID2 with two spares, BASE repair h10.1667-11.1667 vs two-hour DEPOT transport, repair h12.1667-13.1667 and return/restock h15.1667; initial and final stock levels1/2 shown by physical log, all 72 System/Stock aggregate bins and summaries equal and terminal aircraft ready1; aggregate StockTotalResults does not expose on-hand quantity; no ResourceAllocation in same model, reorder, procurement, shortage, category/level interaction, generic POINT, GUI visual or cross-engine claim"
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
        "I01.var03.level_aware_task_binding_apid_matrix.1.0.0")
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
