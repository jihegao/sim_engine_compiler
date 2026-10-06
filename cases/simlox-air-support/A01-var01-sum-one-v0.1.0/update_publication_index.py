"""Append only the bounded A01.var01 sum-to-one fixed-mission observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "A01.var01.sum_one_fixed_mission.0.1.0",
    "case_id": "A01", "variant_id": "A01.var01", "version": "0.1.0", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-aircraft fixed h8-10 A01 mission with only MissionType.TFOUT 0.25-to0.75 changed among 155 authored cells; TFRET0.25 makes the fraction sum exactly1. Accepted A01 final/replay and published TFOUT0 sibling were not rerun. One guarded SSH0/serial-mutex child preserved GUI PID/session/start and completed import/export/exact13-row-containing-table roundtrip/calc/report, converter errors0/warnings108+126/notes0. Physical ID0 mission succeeds h8-10; task starts and completes at h9.5, versus accepted parent's h8.5-9.5 and sibling's h8-9.5. Full72x40 System,72x16 Stock and11 summary fields match accepted parent; source and 34 parent+12 sibling+12 child local raw seals bind the result. Author4130/4130 and separately authored independent4504/4504 GO_BOUNDED. One seed/aircraft/fixed mission/sum-one outbound-plus-return fraction only; TFRET-zero, travel geography, general mission, GUI visual, cross-engine and full A01.var01/Issue18 remain unverified."
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
