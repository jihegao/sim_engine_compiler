"""Append the bounded E15.var07 CLI scope in place."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E15.stock_based_initial_on_hand_below_nominal_reorder_contrast.1.0.1",
    "case_id": "E15",
    "version": "1.0.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded E15 stock-based DU DEPOT reorder pair from accepted G01.var03 donor with E02 prerequisite: both arms TRACK=Y, depot STSIZ4/ROSIZ2 (point2), one-hour LEADT and inherited fixed-seed h10 ordinary depot issue; only arm behavioral difference is depot ISTOH omitted (default4) versus explicit3, which is below nominal4 but above reorder point2; default stock4-to3 after issue stays above point and makes no reorder, explicit stock3-to2 triggers exactly one two-unit h10 reorder delivered h11 as newly created physical IDs5/6, restoring depot to4; physical ID0 arrives base h12 in both, one mission abort and two succeed, terminal aircraft ready1; exact 21-table roundtrips, zero converter errors, four guarded session0 SSH native/selected-report closures with GUI13340 preserved, 28 accepted local raw seals and 72 depot ItemResults bins each, author242/242 and independent1598/1598 GO; earlier v1.0.0 runs excluded because ItemResults absent with TRACK unset; frozen E15.var07 work label does not fulfill catalog E15.var07 explicit-above-nominal boundary, which remains open; one DU/depot/seed/demand only, no ROINT, multiple orders, random leads, at/below-point initial stock, AINST, transfer procurement, GUI visual or cross-engine claim",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    legacy_id = "E15.var07.explicit_initial_on_hand_reorder_contrast.1.0.1"
    legacy = [e for e in doc["entries"] if e["publication_id"] == legacy_id]
    if legacy:
        assert len(legacy) == 1 and legacy[0]["package"] == HERE.name
        lines = raw.splitlines(keepends=True)
        matches = [i for i, line in enumerate(lines) if f'"publication_id": "{legacy_id}"' in line]
        assert len(matches) == 1 and lines[matches[0]].startswith("    {")
        lines[matches[0]] = "    " + json.dumps(ENTRY, ensure_ascii=False) + "\n"
        updated = "".join(lines)
        assert len(json.loads(updated)["entries"]) == len(doc["entries"])
        INDEX.write_text(updated, encoding="utf-8")
        print("replaced prior provisional E15 entry")
        return
    existing = [e for e in doc["entries"] if e["publication_id"] == ENTRY["publication_id"]]
    if existing:
        assert existing == [ENTRY]
        print("already present")
        return
    assert not any(e["package"] == HERE.name for e in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
