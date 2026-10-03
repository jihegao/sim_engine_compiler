"""Append the accepted bounded E11.var05 ignored item-route case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E11.var05.item_specific_route_ignored.1.0.0",
    "case_id": "E11",
    "variant_id": "E11.var05",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E11 autonomous base plus one E07-column-accurate ItemStationStructure row for TEACH-LRU-01 BASE-01→DEPOT-01, SLOW, TFRMS5h/TTOMS7h, null item-specific profile refs and changed description; all 31 other parent tables and general matched DOWN-POLICY h0-9/h11-36 windows fixed. Native guarded SSH0/GUI13340/mutex exact 23-table authored roundtrip; converter Errors0/Warnings #108,#2076,#2077,#445/Notes0, with #445 explicitly saying ItemStationStructure row data ignored for autonomous BASE-01. Child event log byte-identical to accepted E11 parent, both physical transports start/arrive h11 with logged zero travel, one-hour BO clears, aircraft ready h11.3333, depot repair/restock h12. ResultSummary and all 72 half-hour System/Stock rows equal parent; first mission aborts/later two succeed, terminal ready1/BO0. Twelve local raw seals, author and independent read-only replay. One item row/demand/seed/link only; other item routes, policy refs, special tables, GUI visual and cross-engine parity unverified. Other E11 cases and Issue #18 remain open."
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [entry for entry in doc["entries"] if entry["publication_id"] == ENTRY["publication_id"]]
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
