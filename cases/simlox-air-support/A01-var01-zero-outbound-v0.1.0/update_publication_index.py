"""Append only the bounded A01.var01 TFOUT=0 fixed-mission observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "A01.var01.zero_outbound_fixed_mission.0.1.0",
    "case_id": "A01", "variant_id": "A01.var01", "version": "0.1.0", "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded one-aircraft fixed h8-10 A01 mission with only MissionType.TFOUT 0.25-to0 changed among 155 authored cells; accepted A01 final/replay were not rerun. One guarded SSH0/serial-mutex child preserved GUI PID/session/start and completed import/export/exact13-row-containing-table roundtrip/calc/report, converter errors0/warnings108+126/notes0, 12 child plus34 accepted parent raw seals. Physical ID0 mission succeeds h8-10; task starts h8 instead of accepted parent's h8.5 and completes h9.5. All72x40 System,72x16 Stock and11 summary fields match the accepted parent; author4113/4113 and separately authored independent4480/4480 GO_BOUNDED. One seed/aircraft/fixed mission/zero outbound fraction only; sum-to-one and TFRET-zero arms, travel geography, general missions, GUI visual, cross-engine and full A01.var01/Issue18 unverified."
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
