"""Append the accepted bounded D08.var02 PFF CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D08.var02.system_preparation_pff_zero_vs_ten.1.0.0",
    "case_id": "D08",
    "variant_id": "D08.var02",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded matched fixed-seed MissionReliability.PFF zero-versus-ten preparation contrast from accepted D08.var01 default with D02 traditional FRT prerequisite: both item-free two-aircraft arms add one-hour RISK preparation h19-20 and <SYSTEM> reliability row, differ only PFF and description, retain FRT1000000/OPHOURS, MFF, schedule, CM/PM and worker. Zero arm has no preparation fault, launches RISK h20 and aborts on h22.6835 mission fault; positive arm faults aircraft1 h19.2684, substitutes aircraft0, faults again h19.3807 and cancels RISK before launch. One versus two serial 5h direct repairs, two CAL24 PM jobs each, one worker occupied 7 versus12 hours, no stock demand/backorder; both BASIC missions succeed and overall mission success is 2/3 in each arm, with terminal ready2. Two guarded SSH0/GUI13340/mutex closures; exact 24 source-table roundtrips per arm, converter Errors0/Warn108+126/Notes0, 24 local raw seals, author78/78 and independent1049/1049 GO. One seed/high synthetic PFF/item-free system only; no general rate, per-item/failure-mode, calendar, GUI visual or cross-engine claim."
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
