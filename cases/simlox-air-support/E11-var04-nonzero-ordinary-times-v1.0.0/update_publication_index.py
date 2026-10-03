"""Append the accepted bounded E11.var04 ordinary-time contrast."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E11.var04.nonzero_ordinary_times.1.0.0",
    "case_id": "E11",
    "variant_id": "E11.var04",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E11 autonomous base contrast changing only description and BASE-01 StationStructure.TFRMS 2→7 hours and TTOMS 2→11 hours; both matched DOWN-POLICY references, ONDEM h0-9/h11-36 windows, policy values, stock, failure/repair, missions, seed and collection unchanged. Guarded SSH0/GUI13340/mutex native run exact 22-table authored roundtrip; converter Errors0/Warnings #108,#2076,#2077/Notes0 and valid output. Child event log byte-identical to accepted 2/2h parent; both physical transports start and arrive h11 with zero logged travel time, one-hour BO clears h11, aircraft ready h11.3333, depot repair/restock h12. ResultSummary and all 72 half-hour System/Stock rows equal parent; first mission aborts, later two succeed, terminal ready1/BO0/depot positive stock1. Twelve local raw seals, author and independent read-only replay. One ordinary-time contrast/demand/seed/link only; other AUTOM structures, policy parameters, dedicated item transport, GUI visual and cross-engine parity unverified. Other E11 variants and Issue #18 remain open."
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
