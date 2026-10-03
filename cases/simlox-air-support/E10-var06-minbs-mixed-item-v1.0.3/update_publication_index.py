"""Append the accepted bounded E10.var06 mixed-item MINBS supplement."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var06.mixed_item_minbs_pair.1.0.3",
    "case_id": "E10",
    "variant_id": "E10.var06",
    "version": "1.0.3",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var06 same-item-derived mixed-IID MINBS paired structural replication: seed2, two aircraft, two LRU types sharing one general depot-to-base link. Four depot demands form two simultaneous pairs each containing one of each IID. MINBS1 sends four one-item downward tasks; MINBS2 cancels/holds the provisional first task in each pair and sends two physical two-item mixed-IID tasks. Both arms have two-hour spare arrivals, four cleared backorders, four upward failed-item repair/restock cycles, two aborted missions, identical ResultSummary and all 72 System/Stock bins, terminal ready2/backorder0. Fresh guarded SSH0/GUI13340/mutex runs each exact 22-table roundtrip, converter Errors0/Warn108/Notes0, 24 local raw seals and separate independent review. Earlier v1.0.0/v1.0.1/v1.0.2 diagnostics failed their own gates and are disclosed but not published. This is a known fixed-seed replication; no wait or readiness gain, mixed system transport, different transport data, larger threshold, partial horizon batch, GUI visual or cross-engine claim. Full E10, E11 and Issue #18 remain open."
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
