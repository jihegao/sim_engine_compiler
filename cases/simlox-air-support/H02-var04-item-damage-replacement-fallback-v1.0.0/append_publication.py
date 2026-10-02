"""Append the bounded H02.var04 item replacement fallback case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H02.var04.damage_replacement_vs_ordinary_item_replacement_fallback.1.0.0",
    "case_id": "H02", "variant_id": "H02.var04", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted H02.var01 primary-LRU damage parent plus ordinary BASE-01 ItemReplacement SURPT1 in both arms, with DamageReplacement SURPT0.5/E01-SURP retained versus omitted: three identical fixed-seed BATTLE-HIT LRU1/2/3 mission aborts yield three half-hour versus one-hour system replacement tasks, followed by one-hour removed-LRU repairs and stock returns; exact 25/24 authored-table roundtrips, zero converter errors, 72 aligned System/Stock bins each, 1.5 versus 3 system repair aircraft-hours, terminal ready1 and no backorder, 24 sealed raw artifacts, author32/32 and independent7501/7501 GO; one configured station/LRU/seed only, with shortages, multiple consequences, other structures, GUI visual and cross-engine parity unverified"
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
        "H02.var04.system_damage_specific_repair_vs_ordinary_fallback.1.0.0")
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
