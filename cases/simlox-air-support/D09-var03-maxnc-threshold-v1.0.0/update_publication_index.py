"""Append the accepted bounded D09.var03 MAXNC native CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D09.var03.maxnc_2_vs_3_three_installed_lru.1.0.0",
    "case_id": "D09",
    "variant_id": "D09.var03",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed one-aircraft three-identical-installed-LRU MAXNC2 versus3 threshold with D09.var02 parent and D08.var03 noncritical prerequisite; balanced System.FRT9,000,000 equals three Item.FRT3,000,000, Item.CRIT0, NCFTL unset and zero local spares; arm difference only System.MAXNC and description; both first-mission LRU IDs0/1/2 fault at h8.06276/8.16075/8.22615, giving count1 below, count2 equal MAXNC2, count3 exceeds MAXNC2 but equals MAXNC3; MAXNC2 aborts h8.22615 with three C priority tasks, physical same-item repair, first three backorders clear h9.70229, all three missions abort, nine total faults/repairs/demands, terminal BO0/ready1; MAXNC3 succeeds h10 with three NC waiting tasks, all three missions succeed, three faults/zero repairs/three demands, terminal BO3/ready1; threshold escalation inferred from abort/C tasks/repair route and isolated MAXNC delta, without an explicit event-log conversion message; serial guarded session0 SSH preserves GUI13340, zero converter errors/warning108 only, exact 18 authored-table roundtrip per arm, 24 sealed local raw artifacts, 72 System/Stock half-hour bins per arm, author68/68 and independent1099/1099 GO; one seed/high artificial FRT/three installed LRUs/MAXNC2-versus3 only, no general count law, GUI-only or cross-engine claim",
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
