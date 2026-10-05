"""Append the independently accepted bounded D03.var01 one-cycle observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D03.var01.one_calendar_pm_cycle_by_h36.0.1.1",
    "case_id": "D03", "variant_id": "D03.var01", "version": "0.1.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-seed child of accepted D03 calendar PM: 216 parent cell keys with only description and four horizon-end cells changed 60-to-36 hours. Excluded v0.1.0 prelaunch NO_GO for roundtrip gating after calc is preserved with no native run. Sole guarded SSH0 v0.1.1 run has 18-table import/export roundtrip before calc, converter errors0/warnings108+126, three h8/20/32 missions succeeding h10/22/34, one CAL24 PM and one-hour subtask h24-25, and no second PM before h36. Every field of all 72 half-hour System and StockTotal rows matches the accepted parent prefix; 26 ready,35 available,6 mission,1 PM aircraft-hours, final ready1/PM0. Author90/90 and independent5220/5220 GO_BOUNDED. PNB is aggregate, no stocked item. No post-horizon recurrence, GUI visual, cross-engine, generic PM rule or overall D03/Issue18 claim.",
}


def main():
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [x for x in doc["entries"] if x.get("variant_id") == ENTRY["variant_id"]
               or x["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(x["package"] == HERE.name for x in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][:-1] == doc["entries"]
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
