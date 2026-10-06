"""Append the bounded fixed three-threshold panel without replacing earlier arms."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D04.var01.op_hours_two_three_four_fixed_panel.0.2.2",
    "case_id": "D04", "variant_id": "D04.var01", "version": "0.2.2", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-aircraft fixed-seed OPHOURS2/3/4 panel with unchanged h8-10 and h40-41 missions. One PMINT3-to2 cell changes among 221 authored cells in one guarded SSH0/mutex child; accepted OPHOURS3 parent and separately published OPHOURS4 sibling were not rerun. Child missions succeed on physical ID0 and sole PM occurs h10-11, with no h41 PM through h60; parent PM h41-42 and sibling no PM through h60. Converter errors0, two classified warnings, notes0; 12 child plus12 parent plus12 sibling local raw seals and full 120x40 System,120x16 Stock and11 summary fields reconcile. Original v0.2.0 author diagnostic serialization failure and v0.2.1 truncated sibling SHA failure remain preserved and excluded; read-only v0.2.2 author7068/7068 and separate independent7376/7376 GO_BOUNDED. One seed, aircraft, mission schedule and three numeric thresholds only; no direct counter, second complete PM cycle, GUI visual, cross-engine, general threshold or overall Issue18 claim."
}

def main():
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [e for e in doc["entries"] if e["publication_id"] == ENTRY["publication_id"]]
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
    print("appended", ENTRY["publication_id"], len(doc["entries"]), len(doc["entries"]) + 1)

if __name__ == "__main__":
    main()
