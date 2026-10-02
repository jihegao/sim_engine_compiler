"""Append this bounded case to the publication index without reformatting it."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H02.var03.primary_lru_repf_half_eight_seed_repair_discard_realizations.1.0.0",
    "case_id": "H02", "variant_id": "H02.var03", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted H02.var03 REPF1 primary-LRU parent to REPF0.5 with preselected seeds1..8: 23 item-identified damage decisions realize 14 one-hour repairs and 9 discards, including seed7 R/D/R in one run; repaired items either return to local stock or clear waiting backorders directly, while seed1 discards twice and cancels third mission; all eight guarded session0 SSH runs have zero converter errors, exact 24-table authored-row roundtrips, 72 System/Stock bins and 96 sealed raw artifacts, author103/103 and independent30723/30723 GO; four earlier seed1..4 checker-SyntaxError closures and separate prior seed1 discard-only diagnostic excluded and disclosed; small selected deterministic seeds do not estimate 50% frequency or independence, and general fallback, other structures/stations, GUI and cross-engine parity remain unverified"
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
        "H02.var03.primary_lru_repf_zero_discard_vs_one_repair_fixed_seed.1.0.0")
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
