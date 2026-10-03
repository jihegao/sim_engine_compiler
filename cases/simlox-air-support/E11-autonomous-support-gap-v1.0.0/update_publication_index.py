"""Append the accepted bounded E11 autonomous-station publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E11.base.autonomous_support_gap.1.0.0",
    "case_id": "E11",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded E10.var03-derived fixed-seed autonomous BASE-01 with zero local opening spare and one depot spare: change only Station.TYPE WS→AUTOM, StationStructure.PTOMS null→same DOWN-POLICY as PFRMS, and description; ONDEM h0-9/h11-36 isolates base h9-11. Native h9.8829 LRU failure and h10 demand queue both directions until h11, then physical ID0 downward and failed ID1 upward move with zero-hour transport despite ordinary 2h/2h; one-hour backorder, aircraft ready h11.3333, depot ID1 repair/restock h12, one aborted/two successful missions, terminal ready1/backorder0. Guarded SSH0/GUI13340/mutex run exact 22-table authored roundtrip, converter Errors0/Warnings #108,#2076,#2077/Notes0, 12 local raw seals, 72 System/Stock bin reconciliation and independent read-only replay. One gap/demand/seed only; stocked-local behavior, same-time boundary, special route precedence, GUI visual and cross-engine parity unverified. E11 variants and Issue #18 remain open."
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
