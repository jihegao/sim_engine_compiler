"""Append the accepted bounded E12.var07 two-depot DFRAC case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E12.var07.two_physical_depot_dfrac_half.1.0.0",
    "case_id": "E12",
    "variant_id": "E12.var07",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-04.md",
    "scope": "bounded two-actual-depot DFRAC half/half routing from accepted E12.var05 asymmetric-stock parent: DEPOT-02 added as independent one-stock DEPOT-GRP member; both BASE-01/02 gain symmetric general and item-specific links to DEPOT-01/02 at 0.5 each, existing one-hour group ItemRepair covers both; six added rows/five modified cells across five tables, 27 other source tables fixed. Installed manual pp328-329 says DFRAC sum1 probabilistically selects support station for each demand and sends corresponding faulty item to same station. Guarded SSH0/GUI13340/mutex native exact 22-table roundtrip, converter Errors0/Warning108/Notes0, valid output. Four observed propagated failed-LRU demands: BASE-01 ID3→DEPOT-01 at h10.7579, BASE-02 ID4→DEPOT-02 at h11.5, BASE-01 IDs5/6→DEPOT-02 at h23.4473/h35.5; each failed item upward transport matches selected depot. Separate opening depot IDs0/1 supply BASE-01/02; depot01 repairs ID3, depot02 repairs IDs4/5, ID6 still upward in transit h36. BASE-02 local BO h11.5-12.5, no depot BO, ready h13.1667; six missions four abort/two success; all 72 System/Stock bins and terminal boundary reconciled. Twelve sealed local raw files and separate author/independent read-only replay. Four draws do not prove statistical half/half, one graph/seed/item/horizon only; no unit-group expansion, GUI visual or cross-engine claim. Issue #18 remains open."
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
