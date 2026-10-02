"""Append bounded H03.var02 two-mode same-position damage-to-CM publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H03.var02.two_failure_modes_one_position_damage_cm.1.0.0",
    "case_id": "H03", "variant_id": "H03.var02", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted H03.var01 PROB1 position-FM damage mode as byte-identical control; child adds FM-POS-B on same physical POS-A with positive ordinary FRQ1e-9, BATTLE-HIT DamageFailureMode.PROB1, and one-hour BASE-01 direct system CM; each arm has three in-flight BATTLE-HIT events and mission aborts; control one FM-POS-A consequence and half-hour CM per event, child two modes and simultaneous half-hour/one-hour CM tasks per event, partial repair after first and ready after second; 72 aligned System/Stock bins reconcile NDAM3, ordinary NFAIL0, no stock demand/backorder, system repair occupancy 1.5 versus 3.0 aircraft-hours and terminal ready1; two guarded session0 SSH runs, exact 21-table roundtrips, zero converter errors, 24 sealed raw artifacts, author28/28 and independent6631/6631 GO; fixed seed and one position only, no statistical independence, multiple material positions, item-plus-FM consequence, zero ordinary-rate guarantee, GUI visual or cross-engine parity"
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
        "H03.var01.position_failure_mode_damage_direct_cm.1.0.0")
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
