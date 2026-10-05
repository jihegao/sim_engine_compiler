"""Append the independently accepted bounded D03.var03 PMT observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D03.var03.referenced_subtask_overrides_pmt4.0.1.0",
    "case_id": "D03", "variant_id": "D03.var03", "version": "0.1.0",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-seed child of accepted D03 CAL24 PM: 216 parent cell keys with only PMLocation.PMT 1-to-4 hours changed while the referenced sole TaskBreakDown.DURN remains 1 hour. Sole guarded SSH0 child has 18-table import/export roundtrip before calc, converter errors0/warnings108+126, PM starts h24/h49 with one-hour subtasks and completions h25/h50, and three missions h8/20/32 succeeding h10/22/34. Entire model.log and default raw report are byte-identical to accepted D03; all 120 half-hour System and StockTotal rows match every field. Ready49, available58, mission6 and PM2 aircraft-hours. Author95/95 and independent8896/8896 GO_BOUNDED. This is one task-referenced PMT observation, without conflicting missions, GUI visual, cross-engine, generic precedence or overall D03/Issue18 claim.",
}


def main():
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [x for x in doc["entries"] if x.get("variant_id") == ENTRY["variant_id"]
               or x["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(x["package"] == HERE.name for x in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][:-1] == doc["entries"]
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
