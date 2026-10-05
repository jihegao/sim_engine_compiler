"""Append the independently accepted bounded E03.var01 CLI observation."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "E03.var01.single_demand_vs_competing_two_demand.0.1.0",
    "case_id": "E03",
    "variant_id": "E03.var01",
    "version": "0.1.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded fixed-seed single-mission child of accepted E03 two-mission shared-spare parent: only OperationProfile.IQTY 2-to-1 plus description changes. One aircraft mission fails installed LRU ID1 at h8.18829; one demand h8.37658 receives opening spare ID0 without backorder, aircraft ready h8.87658, removed ID1 repairs four hours and restocks h12.5432. Exact 20-table roundtrip, zero converter errors and sole logging warning108, four guarded serial SSH native steps, 12 child plus 12 accepted-parent raw seals, author corrected64/64 plus 579 per-row reconciliation, independent803/803 GO_BOUNDED. Original author63/64 ready-list-order false negative preserved. Two deployed aircraft, one spare, one seed and demand only; changed mission exposure can change random draws; no FIFO, priority, simultaneous-demand, general allocation, GUI visual, cross-engine or full E03/Issue18 claim.",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [item for item in doc["entries"] if item.get("variant_id") == ENTRY["variant_id"] or item["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(item["package"] == HERE.name for item in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
