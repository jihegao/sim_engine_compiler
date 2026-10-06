"""Append the bounded A02.var01 at-return CLI observation once."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "A02.var01.at_return_fixed_missions.0.1.1",
    "case_id": "A02", "variant_id": "A02.var01", "version": "0.1.1", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-aircraft fixed-seed A02 second OperationProfile.STIM h20-to10 among179 authored cells. Accepted A01/A02 parents and excluded v0.1.0 checker failure were not rerun. One guarded SSH0/serial-mutex child preserved GUI PID/session/start and completed import/export/exact13-table roundtrip/calc/report; converter errors0, warnings108+126. At h10 first mission completion, second preassignment, first aircraft arrival, second allocation and second start were observed; missions h8-10,h10-12,h32-34 all succeeded. Full72x40 System,72x16 Stock and11 summary fields reconcile, with flight6 and ready28 hours. Sources and68 accepted parent+9 excluded failed+12 child local raw files are pinned. Frozen author checks4209/4209 were serialized postrun by a separate pinned adapter after a CLI JSON set error; independently authored raw replay4494/4494 GO_BOUNDED did not rely on it. One seed/aircraft/fixed profile only; no general tie-order, other A02.var01 arms, GUI visual, cross-engine or Issue18 completion claim."
}


def main() -> None:
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
