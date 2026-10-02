"""Append the bounded H02.var04 case without reformatting earlier entries."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H02.var04.system_damage_specific_repair_vs_ordinary_fallback.1.0.0",
    "case_id": "H02", "variant_id": "H02.var04", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted H02.var01 system-damage parent plus ordinary BASE-01 SystemRepair DIRPT2 in both arms, with DamageRepair DIRPT1 retained versus omitted: three identical fixed-seed BATTLE-LOSS mission aborts yield three one-hour versus two-hour local system direct repairs; explicit and fallback have exact 18/17 authored-table roundtrips, zero converter errors, 72 aligned System/Stock bins each, 3 versus 6 repair aircraft-hours, terminal ready1, 24 sealed raw artifacts, author29/29 and independent7490/7490 GO; warning #254 says REPF is ignored for system damage; one configured station/system/seed only, and replacement priority, item-level fallback, other structures, GUI visual and cross-engine parity remain unverified"
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
        "H02.var03.primary_lru_repf_half_eight_seed_repair_discard_realizations.1.0.0")
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
