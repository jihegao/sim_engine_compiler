"""Append the accepted bounded E15.var07 above-nominal CLI result."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E15.var07.explicit_above_nominal_initial_stock.1.0.0",
    "case_id": "E15",
    "variant_id": "E15.var07",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded E15.var07 omitted/default versus explicit-above-nominal depot ISTOH: accepted TRACK=Y E15 default parent has opening physical stock4 and new child ISTOH6 exceeds nominal STSIZ4; only child business delta is depot ISTOH null-to6, with PDESC also changed; one DU, depot, ordinary h10 demand, fixed seed, 36h, ROSIZ2 point2 and LEADT1; depot physical stock child6-to5 versus parent4-to3, +2 throughout 72 selected half-hour ItemResults bins, STSZ4/NBO0/NRO0 both, no reorder; h10 depot issue, h12 base replenishment, first mission abort and two later successes, terminal readiness1, selected system/stock/mission summaries equal; 21 authored tables exact roundtrip, zero converter errors, two guarded session0 SSH native/selected-report closures preserve GUI13340, 14 accepted child local raw seals, author123/123 and independent610/610 GO; one explicit above-nominal value/seed/item/demand only, no general reorder law, AINST, ROINT, multiple orders, random lead, transfer procurement, GUI-only or cross-engine claim",
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
