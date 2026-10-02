"""Append the accepted bounded D09.var02 native CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D09.var02.unset_vs_finite_calendar_ncftl_zero_stock.1.0.0",
    "case_id": "D09",
    "variant_id": "D09.var02",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed zero-local-spare traditional LRU Item.NCFTL unset versus accepted D09.var01 finite0.2-hour CALENDAR control, with D08.var03 noncritical prerequisite; new child differs only Item.NCFTL0.2-to-null plus description, retaining NCFTT CALENDAR and STSIZ0; both log h9.8829 noncritical LRU ID0 fault, h10 first-mission success and waiting SURP/local backorder; finite control escalates idle h10.0829, physically removes/repairs same ID0 and clears backorder h11.3329, terminal ready1/backorder0; unset child never escalates or physically repairs through h36, pauses task h19/h31 and resumes h22/h34, succeeds all three missions, has 26 item-hour backorder occupancy and terminal NCF-ready1/backorder1; new guarded session0 SSH run preserves GUI13340, zero converter errors/warning108 only, exact 18 authored-table roundtrip, 12 sealed local raw artifacts and 72 System/Stock half-hour bins, author37/37 and independent745/745 GO; one seed/aircraft/LRU/unset-versus0.2/zero-stock waiting path only, no active repair, alternate supply, MAXNC, GUI-only or cross-engine claim",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [e for e in doc["entries"] if e.get("variant_id") == ENTRY["variant_id"] or e["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(e["package"] == HERE.name for e in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
