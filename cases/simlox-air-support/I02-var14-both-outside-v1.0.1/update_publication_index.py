"""Append the bounded I02.var14 installed-CLI counterexample in place."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "I02.var14.double_OUTSIDE_row_silently_ignored_by_installed_CLI.1.0.1",
    "case_id": "I02",
    "variant_id": "I02.var14",
    "version": "1.0.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-02.md",
    "scope": "bounded manual-versus-installed-CLI counterexample: installed 2017 manual prohibits both ItemTransfer endpoints <OUTSIDE>, but accepted I02.var01 IN parent changing only STTID DEPOT-01-to-<OUTSIDE> plus PDESC roundtrips all 22 populated tables, converts Errors0/Warnings1 and yields a valid SXO with no scheduled h4 transfer; depot ItemResults STSZ/STOHA are one below accepted IN parent in each of 64 half-hour bins h4-36, terminal1/1 versus2/2, while selected mission/system/aggregate stock/summary and default business reports match apart from PDESC and item-position results; guarded session0 SSH native and sealed-SXO report runs preserve GUI13340, two closures/14 accepted raw seals, author24/24 and independent511/511 restricted GO for observed silent handling, NO-GO for expected native rejection; earlier local v1.0.0 rejection-hypothesis probe excluded after its gate failed; one IID/depot/seed/row/build only, no endorsement of prohibited syntax, other rows, GUI visual or cross-engine claim",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
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
