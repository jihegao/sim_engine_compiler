"""Append the accepted bounded D08.var04 SYACF CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D08.var04.risk_syacf_explicit_y_vs_n.1.0.0",
    "case_id": "D08",
    "variant_id": "D08.var04",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded matched fixed-seed RISK MissionType.SYACF explicit Y/N contrast from accepted D08.var01 default with D02 traditional OPHOURS FRT prerequisite: two item-free aircraft, same System FRT1000000, seed1, mission h20-23, repair/PM/worker configuration, only RISK SYACF and description differ. Both aircraft1 critical faults at h22.6835; Y aborts immediately, N continues and succeeds at h23. Both have one direct repair h23-28, two serial CAL24 PM jobs h28-30, one worker occupied7h, no stock demand/backorder, terminal ready2. Mission success 2/3 versus1. Two guarded SSH0/GUI13340/mutex closures; exact 22 source-table roundtrips per arm, converter Errors0/Warn108+126/Notes0, 24 local raw seals, author75/75 and independent1077/1077 GO. One seed/item-free fixed mission only; no general failure-time, noncritical escalation, critical PM/SYACP, GUI visual or cross-engine claim."
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
