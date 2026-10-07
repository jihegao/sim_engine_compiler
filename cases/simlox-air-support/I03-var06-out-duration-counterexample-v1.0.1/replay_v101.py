"""Read the original failed v100 run as a bounded TFDT4 counterexample."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from event_ledger_v101 import parse_log, timeline
from json_codec import parse, typed_equal
from report_oracle_v101 import check_report
from source_gate_v101 import check as check_source
from verify_custody_v101 import verify as verify_custody

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "I03-var06-out-ignored-duration-v1.0.0"
RUN = OLD / "runs" / "i03-var06-out-dt4-v100-ssh-20261008-01"
PARENT = HERE.parent / "I03-var02-idle-crew-out-v1.0.2" / "runs" / "i03-var02-idle-out-v102-ssh-20261007-01"
CONTRACT = parse(HERE / "contract.json")
HISTORY = CONTRACT["historical_failed_run"]
RUN_ID = "i03-var06-out-dt4-v100-ssh-20261008-01"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exact_file(path: Path, item: dict) -> None:
    assert path.is_file() and path.stat().st_size == item["bytes"] and digest(path) == item["sha256"], path


def ordered_process_history(*, steps_override: list[dict] | None = None,
                            invocation_override: dict | None = None) -> dict:
    pins = {Path(item["path"]).name: item for item in HISTORY["v100_raw_run_files"]}
    assert len(pins) == 26
    for name, item in pins.items():
        exact_file(RUN / name, item)
    invocation = parse(RUN / "invocation.json") if invocation_override is None else invocation_override
    closure = parse(RUN / "closure.json")
    failure = parse(RUN / "failure-seal.json")
    steps = parse(RUN / "steps.json") if steps_override is None else steps_override
    manifest = parse(HERE / "preserved-v100-source" / "prelaunch-manifest.json")
    assert invocation["schema"] == "i03-var06-out-dt4-invocation/v1"
    assert closure["schema"] == "i03-var06-out-dt4-closure/v1"
    assert failure["schema"] == "i03-var06-out-dt4-failure-seal/v1"
    assert invocation["run_id"] == closure["run_id"] == failure["run_id"] == RUN_ID
    assert invocation["manifest_sha256"] == closure["manifest_sha256"] == HISTORY["v100_manifest"]["sha256"]
    assert invocation["approval_sha256"] == closure["approval_sha256"] == "2def8ec3afe09bb632730832fa09267d98d5045b58ec344b4ddfbbd81c67a2ff"
    assert closure["invocation_sha256"] == digest(RUN / "invocation.json")
    assert invocation["session_id"] == 0 and type(invocation["session_id"]) is int
    expected_source = {item["key"]: item["sha256"] for item in manifest["source_files"]}
    assert len(expected_source) == 445
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"] == expected_source
    assert closure["error"] == closure["step_error"] == failure["error"] == "child OS exit=1"
    assert closure["publication_state"] == "not_published" and failure["publication_state"] == "excluded"
    raw = closure["raw"]
    assert set(raw) == set(pins) - {"closure.json", "failure-seal.json", "invocation.json"}
    assert len(raw) == 23
    for name, item in raw.items():
        exact_file(RUN / name, item)
    assert set(failure["files"]) == set(pins) - {"failure-seal.json"}
    assert len(failure["files"]) == 25
    for name, item in failure["files"].items():
        exact_file(RUN / name, item)
    assert len(steps) == 6
    native, checkers = invocation["planned_commands"], invocation["planned_checkers"]
    assert [x["name"] for x in native] == ["import", "export", "calc", "jsonreport"]
    assert [x["name"] for x in checkers] == ["check_import_export", "check_behavior"]
    planned = [native[0], native[1], checkers[0], native[2], native[3], checkers[1]]
    assert [x["name"] for x in steps] == [x["name"] for x in planned]
    prior = None
    for ix, (step, command) in enumerate(zip(steps, planned)):
        assert type(step["sequence"]) is int and step["sequence"] == ix
        assert step["program"] == command["program"] and step["arguments"] == command["arguments"]
        assert type(step["child_pid"]) is int and step["child_pid"] > 0
        assert type(step["child_session_id"]) is int and step["child_session_id"] == 0
        assert type(step["exit_code"]) is int and step["exit_code"] == ([0] * 5 + [1])[ix]
        assert step["capture_error"] is None and step["gui_preserved"] is True
        assert step["status"] == ("failed" if ix == 5 else "completed")
        assert step["error"] == ("child OS exit=1" if ix == 5 else None)
        start = datetime.fromisoformat(step["started_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(step["completed_utc"].replace("Z", "+00:00"))
        assert start <= end and (prior is None or prior <= start)
        prior = end
        for kind in ("stdout", "stderr"):
            path = Path(step[kind + "_path"])
            assert path == RUN / path.name and path.name in raw
            assert type(step[kind + "_bytes"]) is int and step[kind + "_bytes"] == raw[path.name]["bytes"]
            assert step[kind + "_sha256"] == raw[path.name]["sha256"]
    receipt = parse(RUN / "roundtrip-validation.json")
    assert receipt["passed"] is True and receipt["issues"] == []
    failed = parse(RUN / "author-validation.json")
    assert set(failed) == {"schema", "passed", "run_id", "error"}
    assert failed["schema"] == "i03-var06-out-dt4-behavior/v1"
    assert failed["run_id"] == RUN_ID and failed["passed"] is False
    assert failed["error"] == "AssertionError: (26, 'resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4')"
    original_reader_stderr = HERE / "preserved-v100-source" / "review" / "independent-postrun-failed.stderr.bin"
    assert b"owned_exact_archive" in original_reader_stderr.read_bytes()
    assert re.findall(r"^Input conversion completed\. Errors: 0, Warnings: 2, Notes: 0$",
                      (RUN / "run.log").read_text(encoding="utf-8-sig"), re.M) == ["Input conversion completed. Errors: 0, Warnings: 2, Notes: 0"]
    return {"native_exit_codes": [x["exit_code"] for x in steps], "actual_session_id": 0,
            "roundtrip_checker_exit": 0, "original_behavior_checker_exit": 1,
            "original_behavior_passed": False, "raw_seals": len(raw), "failure_seal_files": len(failure["files"]),
            "source_before_after_records": len(expected_source)}


def physical_and_reports(child_log: str | None = None, child_report: dict | None = None) -> dict:
    parent_text = (PARENT / "model.log").read_text(encoding="utf-8-sig")
    child_text = (RUN / "model.log").read_text(encoding="utf-8-sig") if child_log is None else child_log
    parent_lines, child_lines = parent_text.splitlines(), child_text.splitlines()
    assert len(parent_lines) == len(child_lines) == 240
    parent_arrival = "Time: 6  resource transfer task 0 (OUT)  arrives with 1 resources"
    child_arrival = "Time: 10  resource transfer task 0 (OUT)  arrives with 1 resources"
    assert parent_lines.count(parent_arrival) == child_lines.count(child_arrival) == 1
    assert parent_arrival not in child_lines and child_arrival not in parent_lines
    p_without = [line for line in parent_lines if line != parent_arrival]
    c_without = [line.replace("resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 4",
                                   "resource transfer task 0 (OUT)  starts with 1 resources, transfer time: 0")
                 for line in child_lines if line != child_arrival]
    assert p_without == c_without, "other complete log line/order/continuation changed"
    parent_timeline = timeline(parse_log(parent_text), 0, 6)
    child_timeline = timeline(parse_log(child_text), 4, 10)
    parent_report = parse(PARENT / "report-raw.json")
    child_report = parse(RUN / "report-raw.json") if child_report is None else child_report
    descriptions = CONTRACT["source_delta"]["allowed_changes_exactly"][0]
    parent_cells = check_report(parent_report, parent_timeline, descriptions["from"])
    child_cells = check_report(child_report, child_timeline, descriptions["to"])
    pt = parent_report["report"]["tables"]
    ct = child_report["report"]["tables"]
    differences = []
    for pa, ch in zip(pt, ct):
        assert pa["name"] == ch["name"] and typed_equal(pa["columns"], ch["columns"])
        pi, ci = pa["instances"][0], ch["instances"][0]
        assert pi["instance_name"] == ci["instance_name"]
        for ri, (prow, crow) in enumerate(zip(pi["rows"], ci["rows"])):
            for column, left, right in zip(pa["columns"], prow, crow):
                if not typed_equal(left, right):
                    differences.append((pa["name"], ri, column["name"], left, right))
    assert differences == [("ProblemDescription", 0, "PDESC", descriptions["from"], descriptions["to"])]
    return {"parent_cells": parent_cells, "child_cells": child_cells,
            "corresponding_non_description_equal": 5209, "authored_description_difference": 1,
            "parent_out_start": 6, "parent_out_arrival": 6,
            "child_out_start": 6, "child_printed_duration": 4, "child_out_arrival": 10,
            "child_derived_in_transfer_interval": [6, 10],
            "terminal_completed_out_task_quantity": child_timeline["terminal_completed_out_quantity"],
            "typed_events_each_arm": parent_timeline["typed_event_records"]}


def replay() -> dict:
    custody = verify_custody()
    source = check_source()
    history = ordered_process_history()
    behavior = physical_and_reports()
    return {"schema": "i03-var06-v101-retrospective-verdict/v1", "decision": "GO_BOUNDED_RETROSPECTIVE_COUNTEREXAMPLE",
            "original_v100_decision": "NO_GO_RUN", "new_native_runs": 0,
            "custody": custody, "source": source, "historical_process": history, "behavior": behavior}


if __name__ == "__main__":
    print(json.dumps(replay(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
