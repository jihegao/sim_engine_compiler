"""Append the accepted bounded E10.var01 transport-policy CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var01.downward_transport_fixed_vs_ondem.1.0.1",
    "case_id": "E10",
    "variant_id": "E10.var01",
    "version": "1.0.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded E04-derived fixed-seed one-demand downward TransportPolicyProfile FIXED versus ONDEM: same h9.8829 LRU critical failure, local/depot demand h10 and physical depot spare ID0; ONDEM dispatch h10/arrival h12/backorder2h/aircraft ready h12.3333 versus FIXED queued to h11/arrival h13/backorder3h/ready h13.3333. Upward faulty ID1 transport h10.1667-12.1667, one-hour depot direct repair, h13.1667 restock unchanged; later h20/h32 missions succeed and no later demand. Both guarded SSH0/GUI13340/mutex runs exact 22-table roundtrip, converter Errors0/Warn108/Notes0, 24 accepted local raw seals, System/Stock 72-bin reconciliation, terminal ready1/backorder0, author86/86 and independent806/806 GO. Frozen v1.0.0 diagnostic was NO-GO for inapplicable ResourceResults clause and remains separately sealed; v1.0.1 used byte-identical inputs with corrected pre-run contract and fresh runs. One seed/demand/departure only; no repeated dispatch, batch/MINBS, nested policy, distribution, GUI visual or cross-engine claim."
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [e for e in doc["entries"] if e.get("variant_id") == ENTRY["variant_id"] or e["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(e["package"] == HERE.name for e in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
