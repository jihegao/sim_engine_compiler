"""Read-only sealed author replay of the one original var11 run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from build import typed_equal
from make_prelaunch_manifest import candidate as manifest_candidate
from make_raw_custody import candidate as raw_candidate
from postrun_context import verify as context_verify
from validate_native_cli import check_sealed
from verify_sources import verify as source_verify

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/i03-var11-out-unarrived-v100-ssh-20261008-01"
MANIFEST = HERE / "prelaunch-manifest.json"
VERDICT = HERE / "author-postrun-verdict.json"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def replay() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    current_manifest = manifest_candidate(mode="sealed")
    assert typed_equal(current_manifest, manifest), "prelaunch manifest drift"
    source = source_verify("sealed", MANIFEST)
    assert source["passed"] is True and source["source_pairs"] == 452
    assert source["original_raw_records"] == 144
    raw = raw_candidate()
    assert raw["accepted_context"] == 118 and raw["excluded_failed_witness"] == 26
    assert raw["new_child_raw"] == 23 and raw["new_child_invocation_and_closure"] == 2
    assert (HERE / "raw-custody-map.json").is_file()
    context = context_verify()
    assert context["passed"] is True and context["records"] == 32
    behavior = check_sealed(RUN)
    captured = json.loads((RUN / "author-validation.json").read_text(encoding="utf-8-sig"))
    # The in-memory oracle uses tuple intervals; its frozen checker emitted
    # JSON arrays. Compare the exact JSON presentation that the child emitted.
    rendered = json.loads(json.dumps({key: behavior[key] for key in captured}))
    assert typed_equal(rendered, captured)
    assert behavior["passed"] is True and behavior["report_cell_checks"] == 5210
    assert behavior["timeline"]["out_departure"] == 6.0
    assert behavior["timeline"]["out_arrival"] is None
    assert behavior["timeline"]["terminal_started_unarrived_task_quantity"] == 1
    assert behavior["timeline"]["terminal_completed_out_task_quantity"] == 0
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    approval = HERE / "review/independent-prelaunch-go.json"
    preflight = HERE / "review/preflight-ssh0-20261007T210756239Z.json"
    assert closure["approval_sha256"] == pin(approval)["sha256"]
    assert closure["approved_preflight_sha256"] == pin(preflight)["sha256"]
    assert closure["manifest_sha256"] == pin(MANIFEST)["sha256"]
    assert len(closure["raw"]) == 23
    return {
        "schema": "i03-var11-author-postrun-replay/v1",
        "decision": "GO_AUTHOR_SEALED_REPLAY_ONLY",
        "independent_outcome_required": True,
        "run_id": RUN.name,
        "new_native_runs": 1,
        "accepted_parent_runs_repeated": 0,
        "prelaunch_manifest_sha256": pin(MANIFEST)["sha256"],
        "approval_sha256": pin(approval)["sha256"],
        "preflight_sha256": pin(preflight)["sha256"],
        "closure_sha256": pin(RUN / "closure.json")["sha256"],
        "invocation_sha256": pin(RUN / "invocation.json")["sha256"],
        "source_pairs": 452,
        "historical_catalog_prefix_checked": 492,
        "prior_original_raw": 144,
        "child_original_run_files": 25,
        "child_raw_files": 23,
        "small_context_copies": 32,
        "report_cells_checked_child": 5210,
        "typed_event_records_child": behavior["typed_event_records"],
        "out_task_started_at": behavior["timeline"]["out_departure"],
        "out_arrival_through_horizon": behavior["timeline"]["out_arrival"],
        "printed_transfer_duration": 40,
        "terminal_started_unarrived_task_quantity": 1,
        "terminal_completed_out_task_quantity": 0,
        "h46_status": "arithmetic only; no observed event",
        "native_and_checker_exit_codes": [0, 0, 0, 0, 0, 0],
    }


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    doc = replay()
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    if sys.argv[1:] == ["--write"]:
        assert not VERDICT.exists(), "preserve original author verdict"
        VERDICT.write_bytes(raw)
    else:
        assert VERDICT.is_file() and VERDICT.read_bytes() == raw
    print(json.dumps({"schema": doc["schema"], "decision": doc["decision"],
                      "child_report_cells": doc["report_cells_checked_child"],
                      "independent_outcome_required": True}, separators=(",", ":")))


if __name__ == "__main__":
    main()
