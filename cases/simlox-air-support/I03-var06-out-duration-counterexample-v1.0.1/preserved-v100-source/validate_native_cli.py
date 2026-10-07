"""Read-only prospective child physical and full-report gate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from datetime import datetime

from build import typed_equal
from check_roundtrip import parse
from event_ledger import parse_log, child_timeline
from report_oracle import check_report

HERE = Path(__file__).resolve().parent
INPUT_SHA = "3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694"
RUN_ID = "i03-var06-out-dt4-v100-ssh-20261008-01"
SCHEMA = "i03-var06-out-dt4-behavior/v1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def converter(text: str) -> None:
    assert len(re.findall(r"^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0$", text, re.M)) == 1
    warnings = re.findall(r"Form:\s*(\w+)\s*\nrec\s*(\d+):\s*\(warning\s*#(\d+)\)", text)
    assert warnings == [("Control", "1", "108"), ("System", "1", "126")], warnings
    assert re.findall(r"\bwarning\s*#(\d+)", text) == ["108", "126"]
    assert not re.findall(r"\b(?:error|notice)\s*#(\d+)", text, re.I)
    assert text.count("Starting simulation") == text.count("Saving results") == 1


def check_raw(run: Path, log: str | None = None, report: dict | None = None) -> dict:
    assert run.name == RUN_ID
    assert digest(run / "input.json") == INPUT_SHA
    assert typed_equal(parse(HERE / "native-input.json"), parse(run / "input.json"))
    if log is None:
        log = (run / "model.log").read_text(encoding="utf-8-sig")
    if report is None:
        report = parse(run / "report-raw.json")
    events = parse_log(log)
    timeline = child_timeline(events)
    converter((run / "run.log").read_text(encoding="utf-8-sig"))
    checks = check_report(report, timeline)
    assert timeline["terminal_free_crew"] == 1
    assert timeline["terminal_outside_crew"] == 1
    assert timeline["terminal_ready_aircraft"] == 2
    return {"schema": SCHEMA, "passed": True, "run_id": RUN_ID, "input_sha256": INPUT_SHA,
            "report_cell_checks": checks, "typed_event_records": len(events), "timeline": timeline}


def check_sealed(run: Path) -> dict:
    result = check_raw(run)
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["schema"] == "i03-var06-out-dt4-closure/v1"
    assert closure["run_id"] == RUN_ID
    assert closure["error"] in (None, "") and closure["step_error"] in (None, "")
    actual_raw = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
    assert set(closure["raw"]) == actual_raw and len(actual_raw) == 23
    for name, item in closure["raw"].items():
        path = run / name
        assert set(item) == {"bytes", "sha256"}
        assert path.is_file() and type(item["bytes"]) is int and path.stat().st_size == item["bytes"] and digest(path) == item["sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    assert invocation["schema"] == "i03-var06-out-dt4-invocation/v1"
    assert invocation["run_id"] == RUN_ID and closure["invocation_sha256"] == digest(run / "invocation.json")
    assert invocation["source_hashes_before"] == closure["source_hashes_before"]
    planned_native = invocation["planned_commands"]
    planned_checkers = invocation["planned_checkers"]
    assert [x["name"] for x in planned_native] == ["import", "export", "calc", "jsonreport"]
    assert [x["name"] for x in planned_checkers] == ["check_import_export", "check_behavior"]
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    assert [step["name"] for step in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    planned = [planned_native[0], planned_native[1], planned_checkers[0],
               planned_native[2], planned_native[3], planned_checkers[1]]
    prior_end = None
    for i, (step, command) in enumerate(zip(steps, planned)):
        assert step["sequence"] == i and type(step["sequence"]) is int
        assert step["program"] == command["program"] and step["arguments"] == command["arguments"]
        assert step["status"] == "completed" and type(step["exit_code"]) is int and step["exit_code"] == 0
        assert type(step["child_pid"]) is int and step["child_pid"] > 0
        assert type(step["child_session_id"]) is int and step["child_session_id"] == 0
        assert step["gui_preserved"] is True and step["capture_error"] in (None, "")
        started = datetime.fromisoformat(step["started_utc"])
        completed = datetime.fromisoformat(step["completed_utc"])
        assert started <= completed and (prior_end is None or prior_end <= started)
        prior_end = completed
        for stream in ("stdout", "stderr"):
            path = Path(step[stream + "_path"])
            assert path.parent.resolve() == run.resolve() and path.name in closure["raw"]
            pin = closure["raw"][path.name]
            assert type(step[stream + "_bytes"]) is int and step[stream + "_bytes"] == pin["bytes"]
            assert step[stream + "_sha256"] == pin["sha256"]
    result["closure_sha256"] = digest(run / "closure.json")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("--sealed", action="store_true")
    args = parser.parse_args()
    try:
        result = check_sealed(args.run) if args.sealed else check_raw(args.run)
    except Exception as exc:
        result = {"schema": SCHEMA, "passed": False, "run_id": args.run.name,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    raise SystemExit(0 if result["passed"] else 1)
