"""Append the accepted bounded E10.var06 same-item MINBS publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var06.same_item_minbs_pair.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var06",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var01 ONDEM-derived same-item MINBS paired contrast: port accepted E03 two-aircraft h8 two-demand pattern to depot-to-base link, stock two spares, compare otherwise identical basic ONDEM MINBS1 vs MINBS2. Distinct depot demands h8.37658/h8.6265; MINBS1 sends one-item transports at each demand, arrivals h10.3766/h10.6265. MINBS2 first one-item task cancels and retains request, then sends both physical IDs in one h8.6265 transport, arrival h10.6265; first backorder grows 2->2.24992h. Two upward repairs and aborted missions reconcile, ResultSummary equal, only bins 16/20/21 differ in 72 System/Stock reports, terminal ready2/backorder0. Guarded SSH0/GUI13340/mutex two runs each exact 22-table authored roundtrip, converter Errors0/Warn108/Notes0, 24 local raw seals and separate independent review. Same item and one link only; mixed item/system batching, larger thresholds, partial horizon batch, GUI visual and cross-engine claims remain unverified."
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
