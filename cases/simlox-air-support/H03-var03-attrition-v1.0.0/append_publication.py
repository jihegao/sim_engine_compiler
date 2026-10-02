"""Append bounded H03.var03 loss and shared-evidence H03.var04 follow-on."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "H03.var03.certain_whole_aircraft_attrition_vs_fm_cm.1.0.0",
    "case_id": "H03", "variant_id": "H03.var03", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-2026-10-02.md",
    "scope": "accepted H03.var01 PROB1 position-FM damage mode as byte-identical control versus child turning FM-POS-A DamageFailureMode.PROB to zero, adding certain BATTLE-HIT DamageItem IID=<ATTRITION>, and updating descriptions; control three in-flight damage/FM/abort/half-hour-CM cycles and terminal ready1, child first-event h8.13665 whole-aircraft loss, first mission abort, later scheduled mission cancellations h20.3333/h32.3333, no FM/CM, terminal lost1/ready0; 72 aligned System/Stock bins show control NDAM3/repair occupancy1.5h versus child logged damage but NDAM0/lost occupancy27.86335h, both ordinary NFAIL0 and no stock demand/backorder; two guarded session0 SSH runs, exact 21/22-table roundtrips, converter errors0, 24 sealed raw artifacts, author26/26 and independent6561/6561 GO; one aircraft, seed and station, coupled consequence-table delta only, no mixed positive FM/item claim, GUI visual or cross-engine parity"
}
FOLLOW_ON = {
    "publication_id": "H03.var04.subsequent_missions_after_attrition.1.0.0",
    "case_id": "H03", "variant_id": "H03.var04", "version": "1.0.0",
    "package": HERE.name,
    "evidence": HERE.name + "/cli-scope-signoff-h03-var04-2026-10-02.md",
    "scope": "shared H03.var03 sealed two-run evidence, not an independent experiment or source delta: control repairs FM-POS-A after each damage and launches fixed missions h8/h20/h32; child loses sole aircraft to BATTLE-HIT <ATTRITION> at h8.13665, aborts first mission, next missions ordered/activated h19/h31 wait and cancel h20.3333/h32.3333 without aircraft allocation or launch; 72-bin System ledger remains lost to h36 and ends lost1/ready0 versus control lost0/ready1, Stock no demand/backorder; author26/26 and independent6561/6561 replay of 24 sealed raw artifacts; one aircraft, fixed three-mission schedule and seed only, no replacement/reconstitution, universal scheduling, GUI visual or cross-engine claim"
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    suffix = "\n  ]\n}\n"
    assert raw.endswith(suffix)
    for entry, predecessor in ((ENTRY, "H03.var02.two_failure_modes_one_position_damage_cm.1.0.0"),
                               (FOLLOW_ON, ENTRY["publication_id"])):
        existing = [item for item in doc["entries"] if item["publication_id"] == entry["publication_id"]]
        if existing:
            assert existing == [entry]
            continue
        assert doc["entries"][-1]["publication_id"] == predecessor
        prefix = raw[:-len(suffix)]
        assert prefix.endswith("}")
        raw = prefix + ",\n    " + json.dumps(entry, ensure_ascii=False) + suffix
        doc = json.loads(raw)
        assert doc["entries"][-1] == entry
    INDEX.write_text(raw, encoding="utf-8", newline="")
    print(FOLLOW_ON["publication_id"], len(doc["entries"]))


if __name__ == "__main__":
    main()
