"""Append the accepted bounded E10.var05 nested-repeat publication."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var05.nested_fixed_repeat.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var05",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var02 flat-FIXED-derived fixed-seed nested transport profile: replace h8/h11 basic rows by DOWN-POLICY -> REPEAT-FIXED at h8 IQTY2/IINT3, child FIXED relative STIM0/TPTIM2. Native scheduled points expand h8 and h11; empty h8 task explicitly cancels with zero items, h10 depot spare ID0 demand queues to h11, dispatches and arrives base h13, BO3h, ready aircraft h13.3333. Entire native event log and all 72 System/Stock bins plus ResultSummary equal accepted flat comparator; upward failed-item repair and later missions unchanged. Guarded SSH0/GUI13340/mutex run exact 22-table authored roundtrip, converter Errors0/Warn108/Notes0, 12 local raw seals and separate independent review. One nested level, one repeated FIXED child and one demand only; no ONDEM child, mixed policy, multiple demands, batching, GUI visual or cross-engine claim."
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [entry for entry in doc["entries"] if entry.get("variant_id") == ENTRY["variant_id"] or entry["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(entry["package"] == HERE.name for entry in doc["entries"])
    newline = "\r\n" if "\r\n" in raw else "\n"
    marker = f"{newline}  ]{newline}}}{newline}"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + "," + newline + "    " + json.dumps(ENTRY, ensure_ascii=False) + newline + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
