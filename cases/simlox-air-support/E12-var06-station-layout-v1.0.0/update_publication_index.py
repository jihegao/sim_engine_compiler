"""Append the accepted bounded E12.var06 Station layout metadata case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E12.var06.station_level_index_metadata.1.0.0",
    "case_id": "E12",
    "variant_id": "E12.var06",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-04.md",
    "scope": "bounded Station.LEVL/LINDX support-organization plot metadata from accepted E12.var05 asymmetric-stock parent: BASE-01=(BASE,2), BASE-02=(BASE,1), DEPOT-01=(DEPOT,1), plus description; seven cells in two tables, 30 other source tables fixed. Installed manual pp323-324 describes LEVL level placement and LINDX horizontal ordering, with distinct BASE/DEPOT levels consistent with support edges. Guarded SSH0/GUI13340/mutex native exact 22-table authored roundtrip, converter Errors0/Warning108/Notes0 and valid output. Child event log byte-identical to parent; ResultSummary and all 72 System/72 Stock bins exactly equal, only report description differs. Six missions four abort/two success, BASE-02 local BO h11.5-15.9246, physical item and terminal boundary preserved. Twelve local raw seals and separate author/independent replay. CLI JSON report lacks the rendered organization plot, so actual visual placement is unverified; this accepts calculation/numeric-report neutrality for one graph/seed/horizon, not general layout, GUI visual or cross-engine behavior. Other E12 cases and Issue #18 remain open."
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
