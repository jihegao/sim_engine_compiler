"""Append the accepted bounded E10.var02 empty-FIXED-departure publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var02.empty_fixed_departure.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var02",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var01 FIXED-derived one-seed downward TransportPolicyProfile: added empty h8 FIXED point explicitly cancels zero-item scheduled task, with no physical shipment before h9.8829 LRU failure and h10 depot spare demand. Same physical spare queues to retained h11 departure, arrives h13, closes local backorder after 3h and restores aircraft readiness h13.3333. Upward failed-item transport, depot repair/restock, two later successful missions, 72 half-hour System/Stock bins and ResultSummary exactly match accepted FIXED parent. Guarded SSH0/GUI13340/mutex native run passes exact 22-table authored roundtrip, converter Errors0/Warn108/Notes0, 12 local raw seals and separate independent review. One empty point and one demand-bearing point only; no same-time priority, multiple demands, batching, nested policy, GUI visual or cross-engine claim."
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
