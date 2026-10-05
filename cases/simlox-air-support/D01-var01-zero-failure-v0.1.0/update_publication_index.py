"""Append the independently accepted bounded D01.var01 CLI observation."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D01.var01.matched_zero_system_item_frt.0.1.0",
    "case_id": "D01", "variant_id": "D01.var01", "version": "0.1.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-seed matched System/Item FRT 300000-to-0 child of accepted installed-LRU D01; description is the only other changed cell among 257 unchanged cell keys. Sole guarded SSH0 native run has exact 18-table roundtrip, converter errors0/warnings108+2053, three planned h8/20/32 missions succeeding at h10/22/34 without observed ordinary failure, replacement demand, repair or stock transition. Opening physical local spare ID0 remains unissued by complete event ledger; terminal on-hand is inferred, not read from aggregate PNB. All 72 system and 72 stock bins reconcile: six flight, 27 ready, 36 available aircraft-hours and zero failure/repair/demand/backorder counters. Accepted parent and child have 12 raw seals each. Original validator prelaunch NO_GO and author53/54 filename false negative are preserved; corrected author54/54 and independent496/496 GO_BOUNDED. Both FRTs changed together; no independent field isolation, other mechanisms, seeds, GUI visual, cross-engine or full D01/Issue18 claim.",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [item for item in doc["entries"] if item.get("variant_id") == ENTRY["variant_id"] or
               item["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(item["package"] == HERE.name for item in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
