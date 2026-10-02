"""Append the accepted bounded D08.var03 native CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D08.var03.traditional_and_failure_mode_criticality_endpoints.1.0.0",
    "case_id": "D08",
    "variant_id": "D08.var03",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed criticality endpoints in two accepted routes: D01 traditional LRU Item.CRIT1-to0 and D06 explicit position FM CRITF1-to0, with D02 catalog prerequisite; criticality-one controls abort the first mission after h9.8829 fault, zero children log it noncritical and succeed at h10, then succeed at h22/34 with one aircraft ready h36; traditional child exchanges spare LRU after return, repairs removed LRU by h11.25, and reconciles 72 System/Stock bins with one failure, repair and stock demand; explicit child has two noncritical FM faults h9.8829/h21.8602 and postreturn CM h10-10.5/h22-22.5, 72 bins with two failures/repairs and no LRU exchange; two guarded session0 SSH runs, 18 authored-table exact roundtrips per arm, zero converter errors and expected warning108, 24 local raw seals, author79/79 and independent1064/1064 GO; one aircraft/seed/three missions and endpoint values only, no fractional criticality, mission overrides, PFF, SYACF, NCFTL escalation, simultaneous faults, GUI-only or cross-engine claim",
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
