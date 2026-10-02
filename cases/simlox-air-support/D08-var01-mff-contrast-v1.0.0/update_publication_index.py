"""Append the accepted bounded D08.var01 native CLI publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D08.var01.mission_type_mff_default_vs_low.1.0.0",
    "case_id": "D08",
    "variant_id": "D08.var01",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed traditional OPHOURS MissionType.MFF contrast: accepted D05 two-aircraft direct-CM/calendar-PM donor and D02 prerequisite, only RISK-MISSION MFF differs omitted/default1 versus explicit0.000001, BASIC-MISSION MFF0 inherited; default repeats D05 h22.6835 critical failure and mission abort, h23-28 direct CM worker booking, serial CAL24 PM h28-30, mission success2/3; low arm has no observed failure or CM, mission success3/3, serial CAL24 PM h24-26; one P-MAINT worker nonoverlap, two aircraft ready h36 both; two guarded session0 SSH native closures preserve GUI13340, 22 authored tables exact roundtrip each, zero converter errors with #108/#126 only, 24 local raw seals, author81/81 and independent1358/1358 GO; one seed/multiplier/schedule only, no reliability rate, override/PFF/criticality/SYACF/GUI-only/cross-engine claim",
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
