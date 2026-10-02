"""Append the accepted bounded D09.var04 shortage-at-escalation CLI case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D09.var04.part_vs_crew_shortage_at_calendar_escalation.1.0.0",
    "case_id": "D09",
    "variant_id": "D09.var04",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed one-aircraft traditional noncritical LRU with NCFTL0.2 CALENDAR and explicit 0.25-hour REMOVE/REPLACE system task requiring one P-CREW on removal; accepted D09.var01 calendar parent and I01.var03 task/resource donor; matched part-short stock0/crew1, crew-short stock1/crew0, supplied stock1/crew1, with each shortage versus supplied changing only its one capacity field plus description; all share h9.8829 noncritical fault and h10 first-mission success; part-short has local backorder and escalates h10.0829, books crew/removes/repairs same failed ID0, clears backorder h11.3329, ready h11.5829 and all missions succeed; crew-short takes a stocked spare for failed ID1 at h10 but fails P-CREW QTY1 availability, escalates h10.0829, remains critical resource-waiting without physical removal/repair or backorder, later missions cancel h20.3333/h32.3333, terminal ready0; supplied books crew and begins active removal h10, does not escalate, task completes h10.5, all missions succeed; stocked spare taking is not installed replacement; serial guarded session0 SSH preserves GUI13340, zero converter errors/warning108 only, exact 23 authored-table roundtrip per arm, 36 sealed local raw artifacts, 72 aligned System/Stock/Resource half-hour bins per arm, author91/91 and independent1841/1841 GO; one seed/aircraft/LRU/task and stock/crew0-1 only, no general shortage-priority, GUI-only or cross-engine claim",
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
