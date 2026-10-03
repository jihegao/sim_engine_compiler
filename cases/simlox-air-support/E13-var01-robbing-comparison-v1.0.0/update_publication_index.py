"""Append one independently accepted E13.var01 paired comparison."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E13.var01.traditional_robbing_matched_control.1.0.0",
    "case_id": "E13", "variant_id": "E13.var01", "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-04.md",
    "scope": "One-seed paired traditional critical subitem robbing case from accepted E03. Two same-unit same-type aircraft, two traditional LRUs A/B, FRT 1.8M+4.2M=System 6M per million operating hours, zero opening spares, A/B local repairs 12/4h. Frozen enabled ENROB=Y and matched ENROB=N inputs differ only in ENROB and description; two prior sealed diagnostic probes excluded from behavioral acceptance. Guarded SSH0/GUI13340/mutex native five-step runs, exact 20-populated-table roundtrips, converter Errors0/Warning108. Both arms fail A0 at h8.09414 and B1 at h8.15663. Enabled run explicitly robs healthy B2 from aircraft0 at h8.47992, recipient aircraft1 receives B2 at h8.64659 and is ready h8.97992; repaired B1 returns to donor at h12.4799. Control has no rob and recipient ready h12.8133. Donor ready h20.6883 in both: 3.83338h recipient benefit without donor delay for this run. Same two mission aborts and ResultSummary; all 72 StockTotalResults rows equal; 42 SystemResults cells differ in bins16-25 including NROBT. Two ready and no backorders terminal. Each paired arm has 12 sealed local raw files; separate author and independent read-only replay. No explicit CM/failure-mode, resource scarcity, stochastic, GUI or cross-engine claim. Issue #18 remains open."
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
