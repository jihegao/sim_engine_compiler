"""Read-only author assessment of the already sealed v101 child; no native call."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import check as check_roundtrip
from validate_native_cli import validate
from verify_sources import HERE, RUN_ID, verify

RUN = HERE / "runs" / RUN_ID
MANIFEST_SHA = "c1c2665b9e8c8a7e054c47395a91110e0f4852605573ca49bc6aa69b2308e6e2"
APPROVAL_SHA = "84fe2b79dba385513ba4781050b452087480065e0f63bcc335291a1f52686e35"
PREFLIGHT_SHA = "38ad650cf9d586e0456922b9fd0b706da9a887b0af7f5a2ee78b63eef9039094"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assess() -> dict:
    source = verify()  # call with --sealed in CLI; historical catalog resolved from exact archive
    assert source["passed"]
    manifest_path = HERE / "prelaunch-manifest.json"
    assert seal(manifest_path)["sha256"] == MANIFEST_SHA
    manifest = read(manifest_path)
    assert len(manifest["source_files"]) == 155
    closure = read(RUN / "closure.json")
    invocation = read(RUN / "invocation.json")
    assert closure["schema"] == "c02-var01-v101-closure/v1"
    assert closure["run_id"] == invocation["run_id"] == RUN_ID
    assert closure["error"] == closure["step_error"] == ""
    assert closure["manifest_sha256"] == invocation["manifest_sha256"] == MANIFEST_SHA
    assert closure["approval_sha256"] == invocation["approval_sha256"] == APPROVAL_SHA
    assert closure["approved_preflight_sha256"] == invocation["approved_preflight_sha256"] == PREFLIGHT_SHA
    assert closure["invocation_sha256"] == seal(RUN / "invocation.json")["sha256"]
    before = closure["source_hashes_before"]
    after = closure["source_hashes_after"]
    assert before == after == invocation["source_hashes_before"]
    assert len(before) == 155
    for spec in manifest["source_files"]:
        assert before[spec["key"]] == spec["sha256"]
        assert seal(Path(spec["path"])) == {"bytes": spec["bytes"], "sha256": spec["sha256"]}
    raw = closure["raw"]
    assert len(raw) == 23
    assert set(raw) == {p.name for p in RUN.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
    for name, spec in raw.items():
        assert seal(RUN / name) == spec
    assert len([p for p in RUN.iterdir() if p.is_file()]) == 25
    steps = read(RUN / "steps.json")
    assert [step["name"] for step in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 and
               type(step["exit_code"]) is int and step["child_session_id"] == 0 and
               type(step["child_pid"]) is int and step["child_pid"] > 0 and
               step["capture_error"] is None and step["gui_preserved"] is True for step in steps)
    roundtrip = check_roundtrip(RUN)
    assert roundtrip["passed"] and roundtrip["authored_row_tables"] == 20
    behavior = validate(RUN)
    assert behavior["passed"] and behavior["report_cell_checks"] == 10420
    assert behavior["child"]["cancellation_token"] == "7.58333"
    stored = read(RUN / "author-validation.json")
    assert stored == behavior
    return {"schema": "c02-var01-v101-author-postrun-assessment/v1",
            "decision": "AUTHOR_EVIDENCE_CONSISTENT_PENDING_INDEPENDENT_REPLAY",
            "new_native_runs": 1, "run_id": RUN_ID,
            "manifest_sha256": MANIFEST_SHA, "closure_sha256": seal(RUN / "closure.json")["sha256"],
            "invocation_sha256": seal(RUN / "invocation.json")["sha256"],
            "raw_seals": len(raw), "run_files": 25, "source_before_after_records": len(before),
            "steps_completed_exit0_session0": len(steps), "roundtrip_row_tables": 20,
            "parent_report_cells": behavior["parent"]["cells"],
            "child_report_cells": behavior["child"]["cells"],
            "cancellation_hour_printed": behavior["child"]["cancellation_hour_printed"],
            "independent_frozen_method_original_status": "parser failed on PS5 UTF-8 BOM closure; correction pending",
            "independent_acceptance": False}


if __name__ == "__main__":
    import sys
    assert "--sealed" in sys.argv, "explicit sealed-readonly mode required"
    print(json.dumps(assess(), sort_keys=True, separators=(",", ":")))
