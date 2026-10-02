"""Append only the independently accepted bounded D14.var01 CLI scope."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D14.var01.monit_y_vs_n_physical_identity.1.0.1",
    "case_id": "D14",
    "variant_id": "D14.var01",
    "version": "1.0.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded fixed-seed one-aircraft, one installed and one stocked LRU, item OPHOURS=2 PM with deterministic scheduled system PMReplacement and local item overhaul; accepted D06 structural parent with D04 PM and E01 stock prerequisites; frozen paired inputs differ only MaterielPM.MONIT Y/N and description; guarded session0 SSH preserves GUI13340, zero conversion errors/warning108 only, exact 20 populated-table roundtrip in both, 24 sealed local raw records, 72 aligned half-hour System/Stock bins per arm, author190/190 and separate read-only reviewer782/782 GO; all three missions succeed, system PM at h10/22/34 and item overhaul after removal; MONIT Y removed/stocked physical IDs cycle [0,1,0]/[1,0,1], MONIT N removed IDs [1,2,3] recreate each time; both report three PM completions, zero failures, six aircraft flight hours, no backorders, terminal ready1 and stock1; v1.0.0 missing-replacement warning243 candidate excluded; item age/counter reset, different prelife, full D14/G11, GUI visual and cross-engine behavior remain unverified",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [e for e in doc["entries"] if e.get("publication_id") == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(e.get("variant_id") == ENTRY["variant_id"] for e in doc["entries"])
    assert not any(e["package"] == HERE.name for e in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
