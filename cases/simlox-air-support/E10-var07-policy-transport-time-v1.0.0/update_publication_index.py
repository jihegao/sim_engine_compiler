"""Append the accepted bounded E10.var07 policy-time contrast."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var07.policy_transport_time.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var07",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var01 ONDEM-derived policy-time pair: both arms set TransportPolicyProfile.TPTIM=3h with StationStructure.TFRMS=2h; exp3 alone sets TPTIMD=<EXP>. Det3 h10 spare dispatch lasts exactly 3h, base arrival h13, backorder3h, aircraft ready h13.3333. Exp3 one logged positive 3.37148h draw, arrival h13.3715, backorder3.37148h, ready h13.7048. One identical first failure/demand, unchanged two-hour upward failed-item shipment and depot repair/restock, one aborted and two successful missions, all 72 half-hour System/Stock bins and terminal readiness/stock/backorder reconcile. Fresh guarded SSH0/GUI13340/mutex runs each exact 22-table authored roundtrip, converter Errors0/Warn108/Notes0, 24 local raw seals, author 89/89 and independent read-only 1224/1224 checks. One draw demonstrates binding, not distribution mean/shape; queued demands, other profiles/distributions, GUI visual and cross-engine claims remain unverified. Full E10, E11 and Issue #18 remain open."
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
