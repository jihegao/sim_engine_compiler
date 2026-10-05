"""Append the accepted bounded publication without reserializing old index bytes."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / "publication-index-v1.json"
TAIL = b"\n  ]\n}\n"
entry = {
    "publication_id": "E15.var04.one_sample_exponential_reorder_lead.1.0.0",
    "case_id": "E15", "variant_id": "E15.var04", "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-05.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded fixed-seed stock-based DU depot random lead from accepted E15 explicit-three parent, sole ItemReorder.LEADTD null-to-<EXP> change with LEADT1 mean. Guarded SSH0/mutex four native stages preserve GUI13340; 21 row-containing tables roundtrip exactly, converter Errors0/Warnings sole #108/Notes0, valid SXO/event/ten-table selected report and 13 local raw SHA seals. One h10 two-item order samples lead1.12383 and completes near h11.1238, delivering physical IDs5/6 after depot ID0 issued h10. All 72 depot half-hour bins reconcile STSZ4, STOHA3-to2, partial h11 bin3.50469446, then4, NRO1 h10 and NBO0; total mean3.65978742 versus fixed-lead parent3.66666675. Only partial bin and total mean differ in selected reports. Author137/137, independently written replay761/761 and separate static bounded GO. One seed/order/draw only; no exponential-law validation, other seeds or concurrent orders, GUI/cross-engine, full E15.var04/E15 or Issue #18 claim."
}

old = TARGET.read_bytes()
data = json.loads(old.decode("utf-8-sig"))
assert len(data["entries"]) == 427
assert data["entries"][-1]["publication_id"] == "E15.var08.equal_reorder_point_observed_after_demand.1.0.1"
assert entry["publication_id"] not in {x["publication_id"] for x in data["entries"]}
assert old.endswith(TAIL)
line = b"\n    ," + json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode() + TAIL
new = old[:-len(TAIL)] + line
updated = json.loads(new.decode("utf-8"))
assert len(updated["entries"]) == 428 and updated["entries"][-1] == entry
TARGET.write_bytes(new)
print(entry["publication_id"])
