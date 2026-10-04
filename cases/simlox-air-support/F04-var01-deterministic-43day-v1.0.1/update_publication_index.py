"""Append this bounded F04 scope without reformatting earlier publications."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "F04.var01.eight_aircraft_43day_no_failure.1.0.1",
    "case_id": "F04",
    "variant_id": "F04.var01",
    "version": "1.0.1",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-04.md",
    "scope": (
        "Bounded accepted F03.var01 staffed-derived eight-aircraft (BASE-01 five, BASE-02 three), "
        "43-day deterministic teaching regression. Exactly 14 changed parent cells across seven tables: "
        "horizon/result end1032, System/LRU/SRU FRT0, deployment5+3, two roots IQTY21/IPER1008 "
        "for 48-hour cadence, and description; mission MFF0 inherited. Two guarded SSH0/GUI13340/mutex "
        "native repeats, exact 30 populated-table roundtrip each, Errors0/Warnings108+2053+2053/Notes0, "
        "24 accepted raw seals. Logs and reports byte-identical: 21 BASE2, 21 RISK and 21 BASIC starts "
        "and successes, 105 sorties, 210 aircraft flight-hours, no fault or stock demand. CAL24 PM "
        "starts324/completes323; terminal h1032 has seven ready, one in PM, one maintainer booked, "
        "zero backorder/queue. All 2064 half-hour System/Stock/Resource bins reconcile; author12450/12450, "
        "independent58364/58364 bounded GO. Earlier v1.0.0 IQTY21/IPER48 compressed requests to "
        "2.2857-hour spacing and is excluded, two diagnostic closures sealed locally. One seed/NREPS1; "
        "stochastic precision, failure-driven support, later F04 variants, GUI/cross-engine and Issue #18 remain open."
    ),
}


def main() -> None:
    raw = INDEX.read_bytes()
    doc = json.loads(raw)
    matches = [entry for entry in doc["entries"]
               if entry["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY], "published F04 scope differs"
        print("publication entry already exact")
        return
    assert len(doc["entries"]) == 369
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    marker = nl + b"  ]" + nl + b"}"
    pos = raw.rfind(marker)
    assert pos > 0
    line = ("    " + json.dumps(ENTRY, ensure_ascii=False, separators=(",", ":"))).encode()
    updated = raw[:pos] + b"," + nl + line + raw[pos:]
    parsed = json.loads(updated)
    assert len(parsed["entries"]) == 370
    assert len({entry["publication_id"] for entry in parsed["entries"]}) == 370
    INDEX.write_bytes(updated)
    print("publication entries 370")


if __name__ == "__main__":
    main()
