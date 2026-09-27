"""Extract native fault, demand, stock, repair and mission events with line anchors.

Backorders are demands, not physical stock. This deliberately does not infer
full installed/repair/transit conservation from aggregate result tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data/local/j35-contract-probes"
TIME = re.compile(r"^Time: (\S+) (.*)$")
RULES = {
    "fault": re.compile(r"critical random failure added"),
    "mission_started": re.compile(r"mission starting, duration:"),
    "mission_cancelled": re.compile(r"mission cancelled:"),
    "mission_success": re.compile(r"mission success:"),
    "stock_initiated": re.compile(r"Stock initiated"),
    "demand_arrived": re.compile(r"Item demand arrives"),
    "stock_taken": re.compile(r"Take replacement item .* from stock"),
    "stock_returned": re.compile(r"Put back replacement item .* to stock"),
    "backorder_added": re.compile(r"Backorder added"),
    "backorder_removed": re.compile(r"Backorder removed"),
    "repair_started": re.compile(r"Start repair of item"),
    "repair_finished": re.compile(r"Finished repair of item"),
    "replacement_arrived": re.compile(r"Replacement item arrives"),
    "failed_item_arrived": re.compile(r"Item requiring maintenance arrives"),
    "replacement_received": re.compile(r"system SURP task .* subitem received"),
    "direct_repair_duration": re.compile(r"direct repair subtask .* starts performing, planned to last for"),
    "system_ready": re.compile(r"System ready <"),
}
EXPECTED_NATIVE_STEPS = ("import", "export", "calc", "jsonreport")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_log(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    events = []
    for line_number, line in enumerate(lines, 1):
        match = TIME.match(line)
        if not match:
            continue
        for kind, pattern in RULES.items():
            if pattern.search(match.group(2)):
                event = {"line": line_number, "time_hours_printed": match.group(1), "kind": kind, "text": line}
                if kind in {"stock_initiated", "stock_taken", "stock_returned", "demand_arrived", "backorder_added", "backorder_removed", "fault", "mission_cancelled"}:
                    event["following_lines"] = [item.strip() for item in lines[line_number:line_number + 3]]
                events.append(event)
                break
    return events


def require_complete_native_steps(steps: object, *, case: str) -> None:
    """Reject partial, reordered, duplicated, or failed native evidence."""
    if not isinstance(steps, list):
        raise ValueError(f"{case}: steps.json must contain a list")
    names = [step.get("name") if isinstance(step, dict) else None for step in steps]
    if names != list(EXPECTED_NATIVE_STEPS):
        raise ValueError(
            f"{case}: expected native steps {list(EXPECTED_NATIVE_STEPS)}, got {names}"
        )
    for step in steps:
        exit_code = step.get("exit_code")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int) or exit_code != 0:
            raise ValueError(f"{case}: native step {step['name']} exit code is {exit_code!r}, expected 0")


def analyze_case(directory: Path) -> dict:
    stem = directory.name
    model_path = directory / f"{stem}.json"
    log_path = directory / f"{stem}.log"
    manifest = json.loads((directory / "provenance.json").read_text(encoding="utf-8-sig"))
    validity = json.loads((directory / "validity.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((directory / "roundtrip-check.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((directory / "steps.json").read_text(encoding="utf-8-sig"))
    require_complete_native_steps(steps, case=stem)
    assert sha256(model_path) == manifest["input_sha256"]
    assert validity["valid"] and validity["conversion_errors"] == 0 and validity["sxo_bytes"] > 4
    assert roundtrip["all_equal"]
    events = parse_log(log_path)
    return {
        "case": stem, "input_sha256": sha256(model_path), "enlog_sha256": sha256(log_path),
        "sxo_sha256": sha256(directory / f"{stem}.sxo"),
        "system_count": manifest["system_count"], "repair_enabled": manifest["repair_enabled"],
        "validation": {"sxo_bytes": validity["sxo_bytes"], "conversion_errors": 0, "roundtrip_all_equal": True},
        "events": events,
        "counts": {kind: sum(event["kind"] == kind for event in events) for kind in RULES},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "p2-native-analysis.json")
    parser.add_argument("--summary", type=Path, help="write a compact reviewable material-event index")
    args = parser.parse_args()
    cases = [analyze_case(path) for path in sorted(BASE.glob("p2c-*")) if (path / "validity.json").exists()]
    repeats = []
    for case in cases:
        if case["case"].endswith("-repeat"):
            original = next((other for other in cases if other["case"] == case["case"].removesuffix("-repeat")), None)
            if original:
                kinds = {"fault", "demand_arrived", "stock_taken", "stock_returned", "backorder_added", "backorder_removed", "repair_started", "repair_finished", "replacement_arrived", "replacement_received", "mission_started", "mission_cancelled", "system_ready"}
                signature = lambda row: [(e["kind"], e["time_hours_printed"], e["text"]) for e in row["events"] if e["kind"] in kinds]
                repeats.append({"original": original["case"], "repeat": case["case"], "input_sha256_equal": original["input_sha256"] == case["input_sha256"], "selected_events_equal": signature(original) == signature(case)})
    result = {"cases": cases, "count": len(cases), "repeat_checks": repeats, "scope": "native first-sample mechanism; no shared Rust RNG or complete physical ledger"}
    args.output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if args.summary:
        selected = {"fault", "demand_arrived", "stock_taken", "stock_returned", "backorder_added", "backorder_removed", "repair_finished", "replacement_arrived", "replacement_received", "mission_cancelled"}
        compact = {
            "scope": result["scope"], "repeat_checks": repeats,
            "cases": [
                {
                    key: case[key]
                    for key in ("case", "input_sha256", "enlog_sha256", "sxo_sha256", "system_count", "repair_enabled", "validation", "counts")
                } | {"events": [
                    {key: e[key] for key in ("line", "time_hours_printed", "kind", "text")}
                    for e in case["events"] if e["kind"] in selected
                ]}
                for case in cases
            ],
        }
        args.summary.write_bytes((json.dumps(compact, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for case in cases:
        print(case["case"], case["counts"])
    print("repeat checks", repeats)


if __name__ == "__main__":
    main()
