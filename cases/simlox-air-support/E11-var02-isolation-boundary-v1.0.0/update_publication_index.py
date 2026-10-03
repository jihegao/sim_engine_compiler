"""Append bounded E11.var02 isolation-boundary publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E11.var02.before_at_after_disconnect.1.0.0",
    "case_id": "E11",
    "variant_id": "E11.var02",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E11 empty-local-stock ONDEM policy window contrast with fixed h10 demand, seed and all non-policy inputs: accepted after arm disconnects h9-11; fresh at arm h10-12; fresh before arm h11-13. Both children change only description and three ONDEM boundary cells. All share first critical failure h9.8829, depot physical spare ID0 and failed ID1. Before and at arms dispatch/receive downward ID0 at h10 with zero travel, add/remove a zero-duration local backorder and ready aircraft h10.5; accepted after queues ID0 to h11, BO1h and ready h11.3333. Before upward ID1 moves h10.1667, repairs/restocks h11.1667; at upward request h10.1667 queues until h12, repairs/restocks h13; after upward moves h11 and restocks h12. Exact-boundary h10 downward dispatch is one source-bound observation, not general event priority. Before/at ResultSummary plus all 72 System/Stock bins equal; relative to after, only System20-22/Stock20-21 differ, BO occupancy1→0h and availability +5/6h; one aborted/two successful missions and terminal ready1/BO0/depot stock1. Two guarded SSH0/GUI13340/mutex runs exact 22-table authored roundtrips, converter Errors0/Warnings #108,#2076,#2077/Notes0, 24 local raw seals and independent read-only replay. One demand/gap/seed/link only; reconnection boundary, repeated demand, GUI visual and cross-engine claims unverified. E11 variants and Issue #18 remain open."
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
