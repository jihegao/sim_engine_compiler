"""Append the bounded negative publication while preserving earlier index bytes."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE.parent / "publication-index-v1.json"
TAIL = b"\n  ]\n}\n"
entry = {
    "publication_id": "E15.var09.timebased_istoh_three_below_nominal_four_rejected.1.0.0",
    "case_id": "E15", "variant_id": "E15.var09", "version": "1.0.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-05.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded converter-negative time-based DU depot case from accepted E15.var01 v1.0.1 equality/default-on-hand comparator (whose v1.0.0 warning-attribution gate remains excluded). Sole child source delta is StockAllocation rec2 ISTOH null-to3 while STSIZ4/ROINT16 remain. Installed manual p447 requires time-based ISTOH>=STSIZ. One unique guarded SSH0/mutex run preserves GUI13340; import/export/calc exit0 and exact 21 row-containing authored tables roundtrip. Converter Errors1/Warnings2/Notes0: StockAllocation rec2 error #377 identifies initial stock on hand too small (ISTOH < STSIZ) at TEACH-DU-01/DEPOT-01; warnings #108/#376. SXO is four bytes; no model.log or selected report, so no child stock simulation claim. Ten local raw SHA/size seals, author44/44, independently written replay267/267 and separate static bounded GO. One item/depot/value/strategy only; no general lower-bound, GUI/cross-engine, full E15.var09/E15 or Issue #18 claim."
}

old = TARGET.read_bytes()
data = json.loads(old.decode("utf-8-sig"))
assert len(data["entries"]) == 428
assert data["entries"][-1]["publication_id"] == "E15.var04.one_sample_exponential_reorder_lead.1.0.0"
assert entry["publication_id"] not in {x["publication_id"] for x in data["entries"]}
assert old.endswith(TAIL)
line = b"\n    ," + json.dumps(entry, ensure_ascii=False, separators=(",", ":")).encode() + TAIL
new = old[:-len(TAIL)] + line
updated = json.loads(new.decode("utf-8"))
assert len(updated["entries"]) == 429 and updated["entries"][-1] == entry
TARGET.write_bytes(new)
print(entry["publication_id"])
