"""Append the independently accepted bounded D01.var03 terminal-repair observation."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D01.var03.system_direct_repair_in_progress_at_horizon.0.1.1",
    "case_id": "D01", "variant_id": "D01.var03", "version": "0.1.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-seed child of accepted D01 system direct repair: 194 parent cell keys with only description, SIMPE/RCEND 36-to-34.375 and global plus MISSION/SYSTEM RCINT 0.5-to-0.125 changed. Excluded v0.1.0 converter #204 diagnostic at horizon34.25 is preserved with nine closure and eleven failure seals. Sole guarded SSH0 v0.1.1 run has 14-table roundtrip, converter errors0/warnings108+126, three h8/20/32 missions, failures9.8829/33.8602, one h22 mission success, and direct-repair task1 working from h34 without its parent h34.5 completion before h34.375. Child and parent event prefixes through child horizon are identical. All 275 System and Stock eighth-hour rows reconcile: final NSYRP1/NSYRY0/NSYA0; 24.5 ready,33.5 available,6 mission,0.875 repair aircraft-hours; two failures and one completed repair. Original author602/604 SYDT-bin prediction is preserved; corrected read-only605/605 and independent721/721 GO_BOUNDED. PNB is aggregate, no stocked item; no post-horizon, GUI visual, cross-engine, generalized rule or overall D01/Issue18 claim.",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [item for item in doc["entries"] if item.get("variant_id") == ENTRY["variant_id"] or
               item["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(item["package"] == HERE.name for item in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][:-1] == doc["entries"]
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
