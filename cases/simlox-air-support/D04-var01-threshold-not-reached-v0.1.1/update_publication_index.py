"""Append the separately reviewed bounded D04.var01 observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D04.var01.three_op_hours_below_four_threshold.0.1.1",
    "case_id": "D04", "variant_id": "D04.var01", "version": "0.1.1", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-aircraft OPHOURS=3 accepted D04 parent versus OPHOURS=4 child with three scheduled mission-hours; only MaterielPM.PMINT 3-to4 changes among 221 authored cells. Earlier v0.1.0 prelaunch NO_GO due omitted D03 source pin is preserved, no native run. One corrected v0.1.1 guarded SSH0/mutex child preserved GUI13340; import/export/exact18-table roundtrip/calc/report complete, converter errors0/warnings108+126/notes0, 12 child plus12 parent raw seals. Missions h8-10 and h40-41 both succeed on physical ID0. Child ready on h41 return and no PM through h60; parent PM h41-42. All120x40 System,120x16 Stock and11 summary fields reconcile; only three System rows differ, Stock/summary identical. Child ready55/available60/flight3/PM0 versus parent ready54/available59/PM1 aircraft-hours. Author7084/7084 and independent8195/8195 GO_BOUNDED. One arm, seed, aircraft and schedule only; full before/at/over panel, general threshold, GUI visual, cross-engine, full D04.var01/D04 and Issue18 unverified."
}

def main():
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [e for e in doc["entries"] if e.get("variant_id") == ENTRY["variant_id"] or e["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(e["package"] == HERE.name for e in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][:-1] == doc["entries"]
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])

if __name__ == "__main__":
    main()
