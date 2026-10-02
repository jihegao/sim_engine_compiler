"""Append the bounded I01.var03 maintenance station selection entry."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var03.maintenance_station_selection.1.0.0",
    "case_id": "I01", "variant_id": "I01.var03", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded task-referenced LRU-CM/BASE repair-station APID selection: accepted I01.var01 stocked parent plus E04 two-hour BASE-DEPOT FAST structural donor; equal BASE spare1/DEPOT spare0 stock under AIR_BASIC/AIR_DEPOT, both points complete LRU-CM/BASE allocation and identical one-hour ItemRepair rows at BASE/DEPOT; source pair changes only APID and description; two guarded native runs, zero converter errors, exact 24-table roundtrips, 24 sealed local raw files, author25/25 and independent2016/2016 GO; same LRU ID1 fails h9.8829, BASE repairs h10.1667-11.1667, DEPOT receives ID1 after two-hour transport and repairs h12.1667-13.1667 before two-hour return and BASE restock h15.1667; aircraft ready h10.5, two later missions succeed and terminal ready1, 72-bin System/Stock reports agree; transport and stock timing are coupled downstream observations, not independent general routing claim; positive category/level filtering, simultaneous three-allocation APID, <NONE> reorder, GUI visual and cross-engine claims unverified"
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    existing = [item for item in doc["entries"] if item["publication_id"] == ENTRY["publication_id"]]
    if existing:
        assert existing == [ENTRY]
        print("entry already present")
        return
    assert doc["entries"][-1]["publication_id"] == (
        "I01.var07.missing_selected_category_error2038.1.0.0")
    suffix = "\n  ]\n}\n"
    assert raw.endswith(suffix)
    prefix = raw[:-len(suffix)]
    assert prefix.endswith("}")
    updated = prefix + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + suffix
    parsed = json.loads(updated)
    assert parsed["entries"][-1] == ENTRY and len(parsed["entries"]) == len(doc["entries"]) + 1
    INDEX.write_text(updated, encoding="utf-8", newline="")
    print(ENTRY["publication_id"], len(parsed["entries"]))


if __name__ == "__main__":
    main()
