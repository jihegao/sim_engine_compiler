"""Append the separately reviewed bounded read-only D04.var02 observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D04.var02.thirty_hour_no_flight_gap_derived.1.0.1",
    "case_id": "D04", "variant_id": "D04.var02", "version": "1.0.1", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded read-only catalog mapping of the already accepted D04 one-aircraft OPHOURS3 parent; no new native run. Sealed h8-10 and h40-41 missions leave a 30-calendar-hour no-flight gap h10-40. All 58 half-hour h10-39 bins are ready1/available1/allocated0/flight0/PM0 (29h); h39-40 is mission-allocated1/ready0/flight0/PM0 (1h), followed by h40-41 flight and the sole PM h41-42 after second return. Complete 120x40 System,120x16 Stock and11 summary shape plus event, converter0/2/0, SSH0/GUI/mutex provenance and12 accepted raw seals verified. Original v1.0.0 contract NO_GO for ambiguous NSYMA-versus-NSYMO reservation gate and two v1.0.1 author-checker failures preserved; corrected author349/349 and independent7287/7287 GO_BOUNDED. One seed/aircraft/gap only; no direct PM counter trace, alternative gap length, general inactivity law, GUI visual, cross-engine, full D04.var02/D04 or Issue18 claim."
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
