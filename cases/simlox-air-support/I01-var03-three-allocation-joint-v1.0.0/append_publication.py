"""Append bounded I01.var03 three-allocation selection."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var03.three_allocation_APID_matrix.1.0.0",
    "case_id": "I01", "variant_id": "I01.var03", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded four-POINT simultaneous StockAllocation, ResourceAllocation and MaintenanceAllocation APID selection from accepted joint stock/maintenance parent and accepted resource-preparation donor: BASE spare size1 with P-CREW2 or size2 with P-CREW3, crossed with BASE/DEPOT failed-LRU repair; all source arms differ only Control.APID and description; four guarded SSH runs, converter errors0, exact 29-table roundtrips, 48 local raw seals, author49/49 and independent GO; three active two-crew preparations, ResourceResults NR2/3 in 72 bins, first h9.8829 failure, spare ID0 issue h10, aircraft ready h10.5, BASE repair h10.1667-11.1667 vs DEPOT two-hour outbound/return route and repair h12.1667-13.1667, first item restocked h15.1667; BASE arms finish third mission and end with stock1/2, DEPOT arms have second failure h33.9619 and aborted third mission, second item outbound at h34.1667 still in transit at h36 and end with stock0/1; all arms end ready1, summary MSUF2/3 BASE versus1/3 DEPOT; StockTotalResults.NBO0 is aggregate and does not negate physical internal DEPOT backorder; stock and crew sizes are correlated, no separate causal effect, shortage, reorder, procurement, generic POINT, GUI visual or cross-engine claim"
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
        "I01.var03.joint_stock_maintenance_APID_matrix.1.0.0")
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
