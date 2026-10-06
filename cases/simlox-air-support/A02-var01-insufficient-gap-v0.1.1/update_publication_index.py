"""Append the bounded A02.var01 insufficient-gap CLI observation once."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "A02.var01.insufficient_gap_cancellation.0.1.1",
    "case_id": "A02", "variant_id": "A02.var01", "version": "0.1.1", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-aircraft fixed-seed A02 second OperationProfile.STIM h20-to9.5 among179 authored cells. Accepted A01/A02 parents and published at-return sibling were not rerun. v0.1.0 prelaunch NO_GO had no native child and is pinned. Sole guarded v0.1.1 SSH0/mutex child preserved GUI PID/session/start, completed import/export/exact13-table roundtrip/calc/report with converter errors0, warnings108+126. Mission1 ordered/waited h8.5, timed out and cancelled h9.83333 before first aircraft h10 return, with no second launch/task/success; missions0/2 h8-10/h32-34 succeeded. Full72x40 System,72x16 Stock and11 summary fields reconcile: flight4h, ready30h, terminal ready1, MTMF/MSTF/MSUF/STMF about2/3. Source and68 parent+12 at-return sibling+3 A12 analogue+12 child local raw seals bind result. Author4229/4229 and independent4538/4538 GO_BOUNDED. One seed/aircraft/fixed profile only; no generic cancellation timing, other A02.var01 arms, GUI visual, cross-engine or Issue18 completion claim."
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
