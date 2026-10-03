"""Append the bounded E10.var08 subprofile ignored-fields case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var08.subprofile_ignored_fields.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var08",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded accepted E10.var05 nested-FIXED-derived subprofile wrapper ignored-field case: root DOWN-POLICY->REPEAT-FIXED adds MINBS7, TPTIM9h and TPTIMD=<EXP> only on wrapper while child FIXED remains TPTIM2h. Native converter Errors0, Warnings #108 and #152 explicitly 'Data Ignored'; exact 22 authored tables roundtrip and full event log byte-identical to accepted parent. h8 empty FIXED task cancels, h10 spare demand queues to h11, travels physical 2h to h13, BO3h, aircraft ready h13.3333. All non-description report tables including 72 System/Stock bins equal parent; upward failed-item repair, one aborted/two successful missions and terminal state reconcile. Fresh guarded SSH0/GUI13340/mutex run, 12 local raw seals, author and independent read-only replay. One wrapper, one child, one demand and seed only; other nesting, ONDEM child, multiple demands, overlap, GUI visual and cross-engine behavior unverified. Full E10, E11 and Issue #18 remain open."
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [entry for entry in doc["entries"] if entry["publication_id"] == ENTRY["publication_id"]]
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
