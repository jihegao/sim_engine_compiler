"""Append the accepted bounded I02.var13 publication without reformatting peers."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I02.var13.terminal_in_transit_or_transfer_backorder.1.0.0",
    "case_id": "I02",
    "variant_id": "I02.var13",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "two separately parented bounded endpoint examples with suppressed mission initiation: accepted I02.var04 TFDT2 BETWEEN h6 has tracked depot ID0 in transit at h7 (depot physical1, base0, one in transit after initial depot1 plus h4 IN1); accepted I02.var05 zero-source h2 BETWEEN has an unremoved one-unit transfer backorder at h3 with no physical item, base nominal STSZ1/on-hand0 and ordinary ItemResults/StockTotalResults NBO0, so transfer queue is log-visible rather than reported as ordinary NBO; four changed tables per parent and 28 identical, two guarded session0 SSH native runs with zero converter errors, exact 22-table roundtrips, four sealed-SXO station reports of 14/6 half-hour bins, six closures/32 local raw seals, GUI13340 preserved, author48/48 and independent420/420 bounded GO; one IID/two stations/seed, h7/h3, zero mission initiation, no general horizon law, active-demand priority, GUI visual or cross-engine claim",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    existing = [e for e in doc["entries"] if e["publication_id"] == ENTRY["publication_id"]]
    if existing:
        assert existing == [ENTRY]
        print("already present")
        return
    assert not any(e["package"] == HERE.name for e in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    encoded = "    " + json.dumps(ENTRY, ensure_ascii=False) + "\n"
    updated = raw[:-len(marker)] + ",\n" + encoded + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
