"""Append the accepted bounded E12.var08 unit-group expansion case."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E12.var08.explicit_equal_priority_unit_group_expansion.1.0.0",
    "case_id": "E12",
    "variant_id": "E12.var08",
    "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-04.md",
    "scope": "Bounded group-owned paired schedule from accepted E12.var05 asymmetric-stock parent: explicit TEACH-GROUP has two equal-PRI=1/XTIME=0 physical members, one aircraft at each base; three IQTY=2/IPER=0 waves create six group-owned one-aircraft missions. Two tables added, three existing changed and 29 fixed. Installed manual pp310-313 and accepted A17 native schema govern the source. Guarded SSH0/GUI13340/mutex native exact 24-table roundtrip, converter Errors0/Warning108/Notes0, valid output. Each wave allocates one distinct aircraft from each member: missions 0/2/4 BASE-01 and 1/3/5 BASE-02; four abort/two success. BASE-01 failed IDs2/4/5 and BASE-02 ID3 retain separate stock and repair paths; BASE-02 and depot backorders start h11.5 and clear h15.9246/h14.9246, BASE-02 ready h16.5912. ResultSummary and all 72 System and Stock bins exactly equal accepted parent for this seed; terminal [35.5,36) ready1 versus h36 event ready2. Twelve sealed local raw files and separate author/independent read-only replay. One seed/equal-priority pair only; no priority, XTIME, implicit-member, GUI or cross-engine claim. Issue #18 remains open."
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
