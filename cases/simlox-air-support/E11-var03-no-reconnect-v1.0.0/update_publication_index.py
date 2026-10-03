"""Append the accepted bounded E11.var03 no-reconnection publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E11.var03.no_reconnection_through_horizon.1.0.0",
    "case_id": "E11",
    "variant_id": "E11.var03",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E11 autonomous zero-local-stock base contrast deleting only the second ONDEM policy row h11-36 plus description, retaining h0-9 connection, first h9.8829 failure, h10 demand, seed, one depot spare, both matched policy references and all other model tables. Converter Errors0/Warnings #108,#2076,#2077/Notes0, valid output and exact 22-table authored roundtrip. Depot physical ID0 removed from stock and queued downward; failed ID1 queued upward; both scheduled tasks retain future sentinel start time and neither physically starts or arrives through h36. Local BO remains from h10 through terminal h36 (26h occupancy), repair waits for spare, aircraft unready/unavailable, no depot repair/restock. First mission aborts and later two cancel; ResultSummary mission success fraction 0 versus accepted h11-reconnection parent 2/3. All 72 System/Stock bins reconcile, terminal ready0/BO1. Guarded SSH0/GUI13340/mutex, 12 local raw seals, independent read-only replay. One demand/link/seed and 36h horizon only; later finite reconnection, repeated demand, GUI visual and cross-engine parity unverified. Other E11 variants and Issue #18 remain open."
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
