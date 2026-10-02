"""Append the bounded I01.var03 level-aware task binding entry."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var03.level_aware_task_binding_apid_matrix.1.0.0",
    "case_id": "I01", "variant_id": "I01.var03", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded four-arm level-aware task binding/APID crossover from accepted I01.var03 station parent: fixed LRU ItemRepair task ID at BASE/DEPOT, two Tasks.TLID cells swapped BASE/ALT with linked LEVL1/2 between layers, complete crossed level allocations at AIR_BASIC/AIR_DEPOT, equal base spare1/depot spare0 and one-hour repairs; exact source 2x2 diff; four serial guarded SSH runs, zero converter errors, exact 24-table roundtrips, 48 sealed local raw files, author45/45 and independent GO; same physical LRU ID1 fails h9.8829, spare ID0 drawn h10, aircraft ready h10.5, level/APID route crosses BASE/DEPOT/DEPOT/BASE with local repair h10.1667-11.1667 versus two-hour transport, depot repair h12.1667-13.1667 and base restock h15.1667; 72-bin System/Stock reports and summaries equal, terminal ready1; TLID label and numeric LEVL effect not isolated, second Task inert, category interaction, live competition, combined three-allocation selection, <NONE> reorder, generic routing, GUI visual and cross-engine behavior unverified"
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
        "I01.var03.category_aware_task_binding_apid_matrix.1.0.0")
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
