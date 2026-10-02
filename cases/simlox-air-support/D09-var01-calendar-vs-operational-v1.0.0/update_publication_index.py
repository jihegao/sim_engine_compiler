"""Append the accepted bounded D09.var01 native CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D09.var01.calendar_vs_operational_ncftl_pending_repair.1.0.0",
    "case_id": "D09",
    "variant_id": "D09.var01",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed traditional-LRU Item.NCFTL0.2 clock contrast from accepted D08.var03 CRIT0 parent with accepted E02 zero-stock precedent: both arms set local STSIZ0, differ only Item.NCFTT CALENDAR versus OPERATION plus description, and share h9.8829 noncritical fault, h10 first-mission success and pending SURP/backorder; calendar escalates while idle h10.0829, removes and repairs the same physical LRU ID0, clears backorder h11.3329 and completes all three missions; operational waits across idle, allocates second mission h19, starts h20, escalates/aborts h20.0829, resumes critical repair after return, clears same-item backorder h21.4158 and succeeds at h34; 72 aligned System/Stock bins per arm reconcile one failure/repair/demand, 1.3329 versus 11.4158 item-hour backorder occupancy, terminal ready1/backorder0 and mission success1 versus2/3; two guarded session0 SSH runs, 18 authored-table exact roundtrips each, zero converter errors/warning108 only, 24 local raw seals, author76/76 and independent1640/1640 GO; one seed/item/aircraft/0.2h/zero-stock waiting path only, no MAXNC, active-maintenance, alternate supply, GUI-only or cross-engine claim",
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
