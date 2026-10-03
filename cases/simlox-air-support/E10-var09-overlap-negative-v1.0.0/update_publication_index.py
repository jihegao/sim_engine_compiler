"""Append the accepted E10.var09 negative conversion boundary."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E10.var09.ondem_overlap_rejection.1.0.0",
    "case_id": "E10",
    "variant_id": "E10.var09",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-03.md",
    "scope": "bounded native negative conversion boundary from accepted zero-error E10.var03 ONDEM control: change only first DOWN-POLICY ONDEM DURN9→12h while second starts h11, creating one-hour h11–12 overlap. Guarded SSH0/GUI13340/mutex input imports/exports all 22 authored populated tables exactly. Native calc returns process exit0 but converter reports TransportPolicyProfile rec1 error #153 'FIX transports during ONDEM period in profile: DOWN-POLICY', Errors1/Warning108/Notes0; SXO is 4 invalid bytes, no event log/report or physical simulation. Source/raw seals, author and independent read-only replay document a version-specific rejection, not zero-error model acceptance. One overlap/two ONDEM rows only; legal same-time boundary, other overlaps/nested profiles, GUI visuals and cross-engine claims unverified. Full E10, E11 and Issue #18 remain open."
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
