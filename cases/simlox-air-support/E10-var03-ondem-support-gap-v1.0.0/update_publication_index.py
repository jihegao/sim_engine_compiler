"""Append the accepted bounded E10.var03 ONDEM support-gap publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var03.ondem_support_gap.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var03",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var01 ONDEM-derived fixed-seed downward TransportPolicyProfile: h0-36 ONDEM window split into h0-9 and h11-36, leaving unsupported h9-11 interval with one h10 spare demand. Native event log shows physical depot spare ID0 retained on h11 scheduled task, dispatch h11, arrival h13, three-hour local backorder and aircraft ready h13.3333; complete event log and all non-description report tables exactly equal accepted E10.var01 FIXED comparator, versus immediate ONDEM parent h10 dispatch/h12 arrival/two-hour backorder. Upward faulty ID1 repair/restock and later mission outcomes unchanged; 72 System/Stock bins and terminal ready1/backorder0 reconcile. Guarded SSH0/GUI13340/mutex run has exact 22-table authored roundtrip, converter Errors0/Warn108/Notes0, 12 local raw seals and separate independent review. One gap and one demand only; no multiple demands, boundary same-time priority, no reopening, autonomous-station, GUI visual or cross-engine claim."
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
