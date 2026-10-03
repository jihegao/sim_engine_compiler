"""Append bounded E11.var01 local-spare publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E11.var01.local_spare_during_isolation.1.0.0",
    "case_id": "E11",
    "variant_id": "E11.var01",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E11 empty-local-stock base contrast changing only BASE-01 TEACH-LRU-01 StockAllocation.STSIZ0→1 plus description, retaining h9-11 autonomous isolation, seed, one depot spare and all other tables. At h9.8829 same LRU type fails (physical ID2 after extra opening spare); local spare ID1 satisfies h10 system demand without backorder, aircraft ready h10.5 before h11 reconnect. Independent depot spare ID0 is ordered to replenish local stock and waits to h11; failed ID2 also queues upward. Both zero-hour physical transports close h11, base stock returns1, depot repairs/restocks ID2 at h12. Compared with accepted zero-local-stock parent, BO occupancy 1→0h and system availability gains 5/6h; only System bins20-22 and Stock bins20-21 differ across 72 half-hour bins, ResultSummary/mission outcomes equal, terminal ready1/backorder0. Guarded SSH0/GUI13340/mutex run exact 22-table authored roundtrip, converter Errors0/Warnings #108,#2076,#2077/Notes0, 12 local raw seals and independent read-only replay. One stocked versus empty first demand only; multiple-fault stock exhaustion, same-time boundaries, GUI visual and cross-engine parity unverified. E11 variants and Issue #18 remain open."
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [entry for entry in doc["entries"] if entry.get("variant_id") == ENTRY["variant_id"] or entry["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(entry["package"] == HERE.name for entry in doc["entries"])
    newline = "\r\n" if "\r\n" in raw else "\n"
    marker = f"{newline}  ]{newline}}}{newline}"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + "," + newline + "    " + json.dumps(ENTRY, ensure_ascii=False) + newline + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
