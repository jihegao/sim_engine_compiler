"""Append bounded H03.var01 position-FM damage-to-CM publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H03.var01.position_failure_mode_damage_direct_cm.1.0.0",
    "case_id": "H03", "variant_id": "H03.var01", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted D06 position-FM direct-CM parent with H02 BATTLE-HIT DamageType/MissionDamage configuration: shared ordinary FM FRQ reduced to positive 1e-9, PROB0 DamageFailureMode control versus PROB1 child; each has three in-flight damage occurrences, control has three mission successes/no FM or CM, child logs three FM-POS-A consequences on POS-A, three mission aborts and three half-hour BASE-01 system CM tasks with readiness restored after each; 72 aligned System/Stock bins per run reconcile NDAM3, zero ordinary failures/stock demand/backorder, 0 versus 1.5 CM aircraft-hours and terminal ready1; two guarded session0 SSH runs, exact 21-table roundtrips, zero converter errors, 24 sealed raw artifacts, author26/26 and independent2087/2087 GO; separate unpublished mixed traditional-LRU/system-owned-FM diagnostic has warning242 incomplete repair/no CM and remains unresolved; one position FM and seed only, no multiple modes, simultaneous item/FM claim, zero ordinary-rate guarantee, GUI visual or cross-engine parity"
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
        "H02.var02.two_direct_lru_prob_half_eight_seed_consequences.1.0.0")
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
