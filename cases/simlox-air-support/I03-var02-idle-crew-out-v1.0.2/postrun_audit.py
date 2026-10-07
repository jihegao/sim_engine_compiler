"""Read-only author replay of the sealed I03.var02 child and source lineage.

This is a postrun audit. It never launches SIMLOX or writes a verdict file.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from validate_native_cli import check_sealed
from verify_sources import verify


HERE = Path(__file__).resolve().parent
RUN_ID = "i03-var02-idle-out-v102-ssh-20261007-01"
MANIFEST = HERE / "prelaunch-manifest-v2.json"
RUN = HERE / "runs" / RUN_ID


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def audit() -> dict:
    manifest = read_json(MANIFEST)
    assert manifest["source_count"] == 179
    source = {item["key"]: item["sha256"] for item in manifest["source_files"]}
    assert len(source) == 179
    provenance = verify("sealed", MANIFEST)
    assert provenance["passed"] is True
    assert provenance["accepted_local_git_pairs"] == 20
    assert provenance["accepted_raw_records"] == 34
    assert provenance["installed_files"] == 3
    result = check_sealed(RUN)
    assert result["report_cell_checks"] == 5210
    assert result["typed_event_records"] == 177

    invocation = read_json(RUN / "invocation.json")
    closure = read_json(RUN / "closure.json")
    assert invocation["run_id"] == closure["run_id"] == RUN_ID
    assert closure["invocation_sha256"] == sha(RUN / "invocation.json")
    assert invocation["manifest_sha256"] == closure["manifest_sha256"] == sha(MANIFEST)
    assert invocation["contract_sha256"] == source["child_contract"]
    assert invocation["input_sha256"] == source["child_input"]
    assert invocation["runner_script_sha256"] == source["runner_script"]
    assert invocation["independent_replay_sha256"] == source["independent_replay"]
    assert invocation["source_hashes_before"] == closure["source_hashes_before"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == source
    assert len(closure["raw"]) == 23
    assert set(closure["raw"]) | {"invocation.json", "closure.json"} == {p.name for p in RUN.iterdir() if p.is_file()}
    assert closure["error"] in (None, "") and closure["step_error"] in (None, "")
    assert closure["approval_sha256"] == invocation["approval_sha256"]
    assert closure["approved_preflight_sha256"] == invocation["approved_preflight_sha256"]

    steps = read_json(RUN / "steps.json")
    assert len(steps) == 6
    assert all(type(step["child_pid"]) is int and step["child_pid"] > 0 for step in steps)
    assert all(type(step["child_session_id"]) is int and step["child_session_id"] == 0 for step in steps)
    assert all(type(step["exit_code"]) is int and step["exit_code"] == 0 for step in steps)
    assert all(step["status"] == "completed" and step["gui_preserved"] is True for step in steps)
    timeline = result["timeline"]
    assert (timeline["out_departure"], timeline["out_arrival"], timeline["transfer_quantity"]) == (6.0, 6.0, 1)
    assert [w["launch"] for w in timeline["waves"]] == [8.5, 20.5]
    assert [w["return"] for w in timeline["waves"]] == [9.5, 21.5]
    return {
        "schema": "i03-var02-v102-author-postrun/v1",
        "decision": "GO_AUTHOR_SEALED_REPLAY",
        "independent_decision": "separate_review_required",
        "run_id": RUN_ID,
        "manifest_sha256": sha(MANIFEST),
        "invocation_sha256": sha(RUN / "invocation.json"),
        "closure_sha256": sha(RUN / "closure.json"),
        "prelaunch_source_records": len(source),
        "native_children": 4,
        "checker_children": 2,
        "all_child_os_exits_zero_session_zero": True,
        "accepted_parent_runs_repeated": 0,
        "report_cells_checked_child": 5210,
        "typed_event_records_child": 177,
        "sealed_raw_records": len(closure["raw"]),
        "physical_observation": {
            "idle_out_departure_hour": timeline["out_departure"],
            "idle_out_arrival_hour": timeline["out_arrival"],
            "first_launch_hour": timeline["waves"][0]["launch"],
            "second_launch_hour": timeline["waves"][1]["launch"],
            "first_return_hour": timeline["waves"][0]["return"],
            "second_return_hour": timeline["waves"][1]["return"],
            "terminal_free_crew": timeline["terminal_free_crew"],
            "terminal_outside_crew": timeline["terminal_outside_crew"],
            "terminal_ready_aircraft": timeline["terminal_ready_aircraft"],
        },
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
