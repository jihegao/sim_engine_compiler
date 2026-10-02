"""Append the bounded negative I01.var07 selected-category converter case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I01.var07.missing_selected_category_error2038.1.0.0",
    "case_id": "I01", "variant_id": "I01.var07", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded predeclared negative converter case for a task-referenced LRU-CM/BASE ItemRepair when selected AIR_ALT POINT contains ALT-CM/BASE/BASE-01 but no matching LRU-CM row: accepted I01.var01 stocked parent, frozen pair differs only APID AIR_BASIC to AIR_ALT plus description, both exact 23 row-containing table roundtrips; fresh AIR_BASIC control converter Errors0, valid SXO/report, failed LRU ID1 DIRP h10.1667-11.1667 returns stock, 72 System/Stock bins; AIR_ALT TaskCategory rec1 error2038, Errors1, four-byte unusable SXO and no simulation log/report despite calc exit0, so no AIR_ALT mission/inventory claim; two guarded session0 SSH runs preserve GUI13340 and seal 12+9 local raw artifacts, author16/16 and independent1084/1084 negative GO; source bytes/descriptions reused from earlier unpublished I01.var03 diagnostic under a new pre-run var07 contract and fresh runs, earlier run IDs excluded; positive I01.var03 category/level/station selection, general missing POINTs, NONE reorder, GUI visual and cross-engine behavior remain unverified"
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
        "I01.var01.resource_only_two_POINT_APID_selection.1.0.0")
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
