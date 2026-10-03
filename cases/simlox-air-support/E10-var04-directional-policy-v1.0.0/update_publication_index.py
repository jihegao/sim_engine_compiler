"""Append the accepted bounded E10.var04 directional transport publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var04.upward_fixed_downward_ondem.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var04",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var01 ONDEM-derived fixed-seed directional policy: downward PFRMS=DOWN-POLICY remains ONDEM h0-36 with spare ID0 demand/dispatch h10, base arrival h12, BO2h, ready aircraft h12.3333; upward PTOMS=UP-POLICY FIXED h11 queues failed ID1 after removal h10.1667, dispatches h11, arrives depot h13, receives one-hour direct repair and restocks h14, versus parent's immediate upward h10.1667-12.1667 and restock h13.1667. Full event ledger shows two transports closed; 72 System/Stock bins and ResultSummary equal parent despite changed depot restock time. Guarded SSH0/GUI13340/mutex run exact 22-table authored roundtrip, converter Errors0/Warn108/Notes0, 12 local raw seals and separate independent review. One request per direction and one FIXED point only; no multiple demands, item-specific profile, TPTIM override precedence, GUI visual or cross-engine claim."
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
