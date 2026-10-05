"""Append the separately reviewed, bounded D03.var02 cancellation observation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "publication-index-v1.json"
ENTRY = {
    "publication_id": "D03.var02.pm_first_mission_cancellation_readonly.0.1.3",
    "case_id": "D03", "variant_id": "D03.var02", "version": "0.1.3",
    "package": HERE.name,
    "evidence": f"{HERE.name}/cli-scope-signoff-2026-10-06.md",
    "evidence_index": f"{HERE.name}/evidence-index.json",
    "scope": "Bounded read-only reanalysis of one preserved D03 calendar-PM child under the predeclared v0.1.1 broad conflict gate. The frozen child changes only the second OperationProfile.STIM 20-to24.5 across 216 positional cells. One prior guarded SSH0/mutex/GUI run, no rerun, exact 18-table roundtrip, converter errors0/warnings108+126/notes0 and 24 parent/child raw seals. Mission ID1 books the sole aircraft h23.5; CAL24 PM takes it h24-25; ID1 cancels h24.8333 without start/completion. Missions ID0/ID2 succeed h8-10/h32-34; PM recurs h49-50. Full 120x40 System, 120x16 Stock and 11 summary fields reconcile with two of three missions succeeding; ready51.5, available58, flight4, PM2 and reserved2.5 aircraft-hours. v0.1.0 contract NO_GO, v0.1.1 prelaunch NO_GO and v0.1.2 mission-first NO_GO_FULL_CONTRACT remain excluded. One seed/aircraft/shift/task only; no general priority, GUI visual, cross-engine or overall D03/Issue18 claim.",
}


def main() -> None:
    raw = INDEX.read_text(encoding="utf-8")
    doc = json.loads(raw)
    matches = [entry for entry in doc["entries"] if entry.get("variant_id") == ENTRY["variant_id"]
               or entry["publication_id"] == ENTRY["publication_id"]]
    if matches:
        assert matches == [ENTRY]
        print("already present")
        return
    assert not any(entry["package"] == HERE.name for entry in doc["entries"])
    marker = "\n  ]\n}\n"
    assert raw.endswith(marker)
    updated = raw[:-len(marker)] + ",\n    " + json.dumps(ENTRY, ensure_ascii=False) + "\n" + marker
    assert json.loads(updated)["entries"][:-1] == doc["entries"]
    assert json.loads(updated)["entries"][-1] == ENTRY
    INDEX.write_text(updated, encoding="utf-8")
    print("appended", ENTRY["publication_id"])


if __name__ == "__main__":
    main()
