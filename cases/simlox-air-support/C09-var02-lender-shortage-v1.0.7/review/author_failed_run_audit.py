"""Read-only author diagnosis of the sealed v1.0.7 failed native run.

This is not an acceptance validator and never changes an original source or raw file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import traceback

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from check_roundtrip import parse  # noqa: E402
from numeric_bounds import compare  # noqa: E402
from physical_ledger import physical  # noqa: E402
from report_oracle import derive  # noqa: E402
from validate_native_cli import description, diagnostics, output_tables_doc  # noqa: E402
from verify_sources import verify  # noqa: E402

RUN = HERE / "runs/c09-var02-v107-shortage-ssh-20261007-01"
CONTROL = HERE.parent / "C09-var02-lender-shortage-v1.0.2/runs/c09-var02-v102-ordinary-ssh-20261007-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_line(log: str, pattern: str) -> tuple[float, str]:
    matches = [line for line in log.splitlines() if re.search(pattern, line)]
    assert len(matches) == 1, (pattern, matches)
    match = re.match(r"Time: ([0-9.]+) ", matches[0])
    assert match, matches[0]
    return float(match.group(1)), matches[0]


def main() -> dict:
    assert RUN.is_dir() and CONTROL.is_dir()
    closure_path = RUN / "closure.json"
    failure_path = RUN / "failure-seal.json"
    assert sha(closure_path) == "e09f5fa2549c088e4c3e25a9dc3acea660cac9e1331f4a012e3acaa981810715"
    assert sha(failure_path) == "1a8cbc59efeeae35bc30af33854bf85121b9cdb73dc5f84b2a20ea4e8650ee3a"
    closure = json.loads(closure_path.read_text(encoding="utf-8-sig"))
    failure = json.loads(failure_path.read_text(encoding="utf-8-sig"))
    invocation = RUN / "invocation.json"
    assert closure["invocation_sha256"] == sha(invocation)
    assert closure["manifest_sha256"] == sha(HERE / "prelaunch-manifest.json")
    assert closure["error"] == failure["error"] == "child OS exit=1"
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["source_hashes_before"]) == 1726
    for name, pin in closure["raw"].items():
        path = RUN / name
        assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], name
    for name, pin in failure["files"].items():
        path = RUN / name
        assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], name
    assert len(closure["raw"]) == 23 and len(failure["files"]) == 25
    steps = json.loads((RUN / "steps.json").read_text(encoding="utf-8-sig"))
    assert [x["name"] for x in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert [x["exit_code"] for x in steps] == [0, 0, 0, 0, 0, 1]
    assert [x["status"] for x in steps] == ["completed"] * 5 + ["failed"]
    assert all(x["child_session_id"] == 0 and x["capture_error"] is None and x["gui_preserved"] for x in steps)
    assert all(isinstance(x["child_pid"], int) and x["child_pid"] > 0 for x in steps)
    verifier = verify(mode="sealed_replay")
    roundtrip = json.loads((RUN / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    assert roundtrip["passed"] is True and roundtrip["authored_row_tables"] == 25 and not roundtrip["issues"]
    assert roundtrip["source_sha256"] == sha(HERE / "shortage-input.json")
    assert roundtrip["export_sha256"] == sha(RUN / "roundtrip-raw.json")
    assert json.loads((RUN / "author-validation.json").read_text(encoding="utf-8-sig")) == {
        "error": "AssertionError: ", "passed": False, "schema": "c09-var02-v107-author-validation/v1"}
    diagnostics((RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace"))

    control_log = (CONTROL / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    child_log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    pattern_start = r"return resource transport task 0 starts with 1 resources, transportation time: 0\.5"
    pattern_arrive = r"return resource transport task 0 arrives with 1 resources"
    cstart, cstart_line = event_line(control_log, pattern_start)
    carrive, carrive_line = event_line(control_log, pattern_arrive)
    start, start_line = event_line(child_log, pattern_start)
    arrive, arrive_line = event_line(child_log, pattern_arrive)
    assert (cstart, carrive, start, arrive) == (9.46988, 9.96988, 9.46988, 9.59488)
    pm_start, pm_start_line = event_line(child_log, r"subtask 3 seqno 1 within system PM task 3 on <HOME-AIR,2> starts performing")
    pm_end, pm_end_line = event_line(child_log, r"Time: [0-9.]+  system PM task 3 on <HOME-AIR,2> completed")
    assert (pm_start, pm_end) == (9.59488, 9.84488)
    physical_failure = None
    try:
        physical(child_log, "shortage")
    except AssertionError as exc:
        frames = traceback.extract_tb(exc.__traceback__)
        frame = next((x for x in frames if x.name == "physical" and x.filename.endswith("physical_ledger.py")), None)
        assert frame is not None and frame.lineno == 81, frames
        physical_failure = {"file": "physical_ledger.py", "line": frame.lineno,
                            "gate": "annotated return duration equals printed start-to-arrival elapsed"}
    assert physical_failure

    # A changed annotation in memory only localizes the first frozen gate.
    # It is deliberately not raw evidence or an accepted rewritten log.
    needle = "return resource transport task 0 starts with 1 resources, transportation time: 0.5"
    assert child_log.count(needle) == 1
    synthetic = child_log.replace(needle, needle.replace("0.5", "0.125"))
    synthetic_ledger = physical(synthetic, "shortage")
    assert synthetic_ledger["qualifying_return_hours"] == [0.125]

    actual = output_tables_doc(parse(RUN / "report-raw.json"))
    expected, edges = derive(child_log, horizon=12, fleet=3,
                             description=description(HERE / "shortage-input.json"), with_edges=True)
    assert edges["terminal_closed"] is True
    # The printed HOME PM h9 wait and typed return receipt prove this specific
    # conditional comparison context. The frozen physical checker rejects first.
    edges["special_home_boundary_valid"] = True
    errors, cells = compare(expected, actual, edges=edges, log=child_log)
    assert cells == 1754 and not errors, errors[:10]
    return {"schema": "c09-var02-v107-author-failed-run-audit/v1",
            "decision": "NO_GO_FROZEN_BEHAVIOR_GATE", "native_reruns": 0,
            "closure_sha256": sha(closure_path), "failure_seal_sha256": sha(failure_path),
            "source_pins": 1726, "closure_raw_seals": 23, "failure_file_seals": 25,
            "steps": [{"name": x["name"], "status": x["status"], "exit_code": x["exit_code"],
                       "child_session_id": x["child_session_id"]} for x in steps],
            "source_verifier_passed": verifier["passed"], "roundtrip_row_tables": 25,
            "annotation_hours_control": 0.5, "elapsed_hours_control": carrive - cstart,
            "annotation_hours_child": 0.5, "elapsed_hours_child": arrive - start,
            "return_start_line_control": cstart_line, "return_arrival_line_control": carrive_line,
            "return_start_line_child": start_line, "return_arrival_line_child": arrive_line,
            "home_pm_start_line_child": pm_start_line, "home_pm_completed_line_child": pm_end_line,
            "frozen_physical_first_failure": physical_failure,
            "annotation_only_synthetic_physical_pass": True,
            "author_oracle_cells_diagnostic": cells, "author_oracle_cell_errors_diagnostic": len(errors),
            "terminal_closed_diagnostic": edges["terminal_closed"],
            "limits": "Author read-only diagnosis; synthetic annotation patch is in memory only and does not accept the frozen run."}


if __name__ == "__main__":
    payload = json.dumps(main(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if len(sys.argv) == 3 and sys.argv[1] == "--output":
        target = Path(sys.argv[2]).resolve()
        assert target.parent == Path(__file__).resolve().parent
        assert not target.exists()
        target.write_bytes(payload.encode("utf-8"))
    elif len(sys.argv) == 1:
        print(payload, end="")
    else:
        raise SystemExit("usage: author_failed_run_audit.py [--output NEW_REVIEW_JSON]")
