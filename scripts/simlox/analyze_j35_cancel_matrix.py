"""Extract line-addressable task, PM, preparation and resource evidence from P1 ENLOG.

This reads only validated coordinator-p1-* runs. Printed SIMLOX hours retain
their source precision; no event time is inferred from a log line number.
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
PATTERNS = {
    "pm_started": re.compile(r"^\s*system PM task .* started"),
    "pm_completed": re.compile(r"^\s*system PM task .* completed"),
    "mission_ordered": re.compile(r"mission ordered:"),
    "mission_activated": re.compile(r"mission activated,"),
    "mission_waiting": re.compile(r"mission waiting:\s+timeout at"),
    "system_allocated": re.compile(r"mission allocates system:"),
    "preparation_started": re.compile(r"preparation started, mission:"),
    "preparation_ended": re.compile(r"preparation ended, mission:"),
    "preparation_task_completed": re.compile(r"system preparation task .* completed"),
    "preparation_task_stopped": re.compile(r"system preparation task .* stopped"),
    "step_completed": re.compile(r"subtask .* seqno \d+ within system preparation task .* completed"),
    "step_stopped": re.compile(r"subtask .* seqno \d+ within system preparation task .* ordered to stop"),
    "mission_started": re.compile(r"mission starting, duration:"),
    "mission_cancelled": re.compile(r"mission cancelled:"),
    "resource_allocated": re.compile(r"<(PERSONNEL|DEVICE) at .* allocated to maintenance task:"),
    "resource_released": re.compile(r"<(PERSONNEL|DEVICE) at .* deallocated from  maintenance task:"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(model: dict, name: str) -> list[dict]:
    table = next(item for item in model["model"]["tables"] if item["name"] == name)
    names = [item["name"] for item in table["columns"]]
    return [dict(zip(names, raw)) for instance in table["instances"] for raw in instance["rows"]]


def parse_log(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    events = []
    for line_number, line in enumerate(lines, 1):
        match = TIME.match(line)
        if not match:
            continue
        text = match.group(2)
        for kind, pattern in PATTERNS.items():
            if pattern.search(text):
                event = {"line": line_number, "time_hours_printed": match.group(1), "kind": kind, "text": line}
                if kind == "mission_cancelled":
                    event["snapshot"] = [item.strip() for item in lines[line_number:line_number + 5]]
                events.append(event)
                break
    return events


def analyze_case(directory: Path) -> dict:
    stem = directory.name
    model_path = directory / f"{stem}.json"
    log_path = directory / f"{stem}.log"
    provenance = json.loads((directory / "provenance.json").read_text(encoding="utf-8-sig"))
    validity = json.loads((directory / "validity.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((directory / "roundtrip-check.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((directory / "steps.json").read_text(encoding="utf-8-sig"))
    assert validity["valid"] and validity["conversion_errors"] == 0 and validity["sxo_bytes"] > 4
    assert roundtrip["all_equal"] and all(item["exit_code"] == 0 for item in steps)
    assert sha256(model_path) == provenance["input_sha256"]
    model = json.loads(model_path.read_text(encoding="utf-8-sig"))
    profile = rows(model, "OperationProfile")
    prep = rows(model, "MissionPreparation")
    pm_steps = [row for row in rows(model, "TaskBreakDown") if row["TID"] == "PM_25H"]
    events = parse_log(log_path)
    outcomes = [event for event in events if event["kind"] in {"mission_started", "mission_cancelled"}]
    return {
        "case": stem,
        "input_sha256": sha256(model_path),
        "enlog_sha256": sha256(log_path),
        "sxo_sha256": sha256(directory / f"{stem}.sxo"),
        "validation": {"conversion_errors": validity["conversion_errors"], "sxo_bytes": validity["sxo_bytes"], "roundtrip_all_equal": True},
        "operation_profile": [{key: row[key] for key in ("STIM", "DTIM") if key in row} for row in profile],
        "preparation_durn_hours": [row["DURN"] for row in prep],
        "pm_task_step_durn_hours": [row["DURN"] for row in pm_steps],
        "pm_location_pmt_hours": [row["PMT"] for row in rows(model, "PMLocation")],
        "events": events,
        "outcomes": outcomes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=BASE / "p1-native-analysis.json")
    parser.add_argument("--summary", type=Path, help="write a compact reviewable event index")
    args = parser.parse_args()
    directories = sorted(list(BASE.glob("coordinator-p1-*")) + list(BASE.glob("p1v2-*")))
    cases = [analyze_case(path) for path in directories if (path / "validity.json").exists()]
    result = {"cases": cases, "count": len(cases), "scope": "printed ENLOG times and line numbers; no RNG equivalence implied"}
    args.output.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    if args.summary:
        compact = {
            "scope": result["scope"],
            "native_validation": "four CLI steps exit 0, conversion errors 0, SXO > 4 bytes, nonempty business rows roundtrip equal",
            "cases": [
                {
                    "case": case["case"], "input_sha256": case["input_sha256"],
                    "enlog_sha256": case["enlog_sha256"], "sxo_sha256": case["sxo_sha256"],
                    "validation": case["validation"], "operation_profile": case["operation_profile"],
                    "preparation_durn_hours": case["preparation_durn_hours"],
                    "pm_task_step_durn_hours": case["pm_task_step_durn_hours"],
                    "pm_completed": [
                        {key: e[key] for key in ("line", "time_hours_printed")}
                        for e in case["events"] if e["kind"] == "pm_completed"
                    ],
                    "outcomes": [
                        {key: e[key] for key in ("line", "time_hours_printed", "kind")}
                        for e in case["outcomes"]
                    ],
                }
                for case in cases
            ],
        }
        args.summary.write_bytes((json.dumps(compact, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    for case in cases:
        print(case["case"], "PM", [(e["time_hours_printed"], e["line"]) for e in case["events"] if e["kind"] == "pm_completed"], "outcomes", [(e["kind"], e["time_hours_printed"], e["line"]) for e in case["outcomes"]])


if __name__ == "__main__":
    main()
