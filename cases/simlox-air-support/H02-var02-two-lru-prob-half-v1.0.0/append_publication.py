"""Append the bounded H02.var02 two-LRU consequence cohort."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H02.var02.two_direct_lru_prob_half_eight_seed_consequences.1.0.0",
    "case_id": "H02", "variant_id": "H02.var02", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted H02.var01 primary-LRU damage parent with two identical directly mounted LRUs and two local spares: PROB0 control keeps three BATTLE-HIT events with no item damage and three mission successes; eight preselected PROB0.5 seeds yield 4 zero-, 12 one- and 8 two-item consequences in 24 damage events, with 28 physical LRU decisions, matching spare issues, one-hour removed-item repairs and stock returns; one or two consequential replacement tasks occupy a half-hour aircraft repair window per affected mission; nine guarded session0 SSH runs, exact 24-table authored-row roundtrips and zero converter errors each, 72 System/Stock bins per run, 108 sealed raw artifacts, author113/113 and independent 598/598 source plus 33129/33129 ledger GO; selected deterministic outcomes do not estimate probability or prove independence, and other structures, shortages, GUI visual and cross-engine parity remain unverified"
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
        "H02.var04.damage_replacement_vs_ordinary_item_replacement_fallback.1.0.0")
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
