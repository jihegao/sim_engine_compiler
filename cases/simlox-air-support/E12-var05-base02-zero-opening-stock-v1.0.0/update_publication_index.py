"""Append the accepted bounded E12.var05 asymmetric-stock case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E12.var05.base02_zero_opening_stock.1.0.0",
    "case_id": "E12",
    "variant_id": "E12.var05",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E12.var04 parent to asymmetric opening LRU stock: BASE-02 StockAllocation.STSIZ 1→0 and description only, 30 other source tables fixed; BASE-01 and depot each retain one opening spare, group ItemRepair and BASE-02 one-hour individual SystemRepair fixed. Guarded SSH0/GUI13340/mutex native, exact 22-table authored roundtrip, converter Errors0/Warning108/Notes0 and valid output. Opening depot ID0/BASE-01 ID1/BASE-02 none. First faults BASE-01 h9.8829 and BASE-02 h11.1325; BASE-01 local ID1 used and ready h11.2579. BASE-02 one-hour repair pauses after removal for local backorder h11.5–15.9246; separate depot BO h11.5–14.9246; repaired failed BASE-01 ID2 arrives BASE-02 h15.9246, fit and ready h16.5912. Six missions four abort/two success. ResultSummary equal parent; System bins23–33 and Stock bins23–31 differ; aggregate NBO tracks local BASE-02 shortage, not separately depot BO. Final [35.5,36) ready1 versus exact h36 ready2, failed ID5 in transit. Twelve local raw seals, author60/60 and independent4395/4395 all 72 System/Stock bins. One seed/item/two bases/36h only; changed item numbering may change later random draws, no general allocation policy, resource, GUI visual or cross-engine claim. Other E12 cases and Issue #18 remain open."
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
