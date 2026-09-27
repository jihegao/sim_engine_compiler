"""Build the 26-case planned index; only A01/A02 have implementations."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("A01", "one aircraft, one mission", None, "basic mission generation/start/completion"),
    ("A02", "one aircraft, repeated missions", "A01", "non-overlapping repetition and recovery"),
    ("A03", "multi-aircraft formation", "A02", "required aircraft and sorties"),
    ("A04", "multi-day waves and minimum launch count", "A03", "generation and unmet demand"),
    ("B01", "fixed pre-mission preparation", "A01", "preparation trigger"),
    ("B02", "serial preparation steps", "B01", "work sequence and duration"),
    ("B03", "first and repeat sortie preparation", "B02", "different preparation triggers"),
    ("B04", "turnaround and cross-day work", "B03", "post-flight and day boundary"),
    ("C01", "personnel specialty and quantity", "B02", "personnel demand"),
    ("C02", "equipment and personnel", "C01", "joint resource demand"),
    ("C03", "shared resource competition", "C02", "waiting and release"),
    ("C04", "delay, cancellation and release", "C03", "deadline and cancellation accounting"),
    ("D01", "one component failure and repair", "A01", "fault and repair"),
    ("D02", "flight and calendar fault clocks", "D01", "exposure clock"),
    ("D03", "calendar preventive maintenance", "D01", "calendar PM"),
    ("D04", "flight-hour preventive maintenance", "D03", "flying-hour PM"),
    ("D05", "fault, PM and mission competition", "D04", "same-time priority and mission impact"),
    ("E01", "local spare replacement", "D01", "stock demand and consumption"),
    ("E02", "zero stock and backorder", "E01", "backorder and aircraft waiting"),
    ("E03", "two aircraft sharing one spare", "E02", "unique stock allocation"),
    ("E04", "upstream transport", "E03", "supply route and transit"),
    ("E05", "repair return and reuse", "E04", "return of repaired physical item"),
    ("F01", "nested components and repair levels", "E05", "physical replacement boundary"),
    ("F02", "multi-aircraft multi-cycle support", "F01", "combined support mechanisms"),
    ("F03", "multiple bases", "F02", "site-specific capacity and supply"),
    ("F04", "eight aircraft, 43 days", "F03", "full combined long-horizon case"),
]


def build() -> dict:
    if len(CASES) != 26 or len({entry[0] for entry in CASES}) != 26:
        raise ValueError("issue #18 catalog must contain 26 unique cases")
    entries = []
    for case_id, title, parent, delta in CASES:
        implemented = case_id in ("A01", "A02")
        entries.append({"case_id": case_id, "title": title, "version": "1.0.0" if implemented else None,
                        "parent_case": f"{parent}@1.0.0" if implemented and parent else parent,
                        "delta": delta, "requires": [parent] if parent else [],
                        "status": "cli_behavior_verified_gui_pending" if implemented else "planned",
                        "verified_features": (["one-aircraft mission notice, launch, completion and ready return"] if case_id == "A01"
                                              else ["same stable aircraft reused for three non-overlapping scheduled missions"])
                                             if implemented else [],
                        "cross_engine_status": "unverified",
                        "artifact_ref": f"{case_id}-" + ("single-aircraft-single-mission" if case_id == "A01" else "single-aircraft-repeated-missions") if implemented else None})
    return {"catalog_version": "1.0.0", "source_issue": "#18", "case_count": len(entries),
            "scope": "A01/A02 native CLI normal path verified, GUI publication pending; A03-F04 planned; no J35 equivalence", "cases": entries}


def main() -> None:
    path = ROOT / "catalog.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes((json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(path)


if __name__ == "__main__":
    main()
