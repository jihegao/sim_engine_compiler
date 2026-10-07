"""Read-only reviewer diagnosis of the excluded v107 run; never accepts it.

Only an in-memory copy of the model log has its printed return-duration label
changed to let the previously frozen reviewer parser analyze the event edges.
The original raw label and SHA remain explicit failed observations.
"""
from __future__ import annotations

import hashlib
import json
import runpy
from copy import deepcopy
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
RUN = PKG / "runs/c09-var02-v107-shortage-ssh-20261007-01"
REVIEWER = PKG / "review/independent_replay.py"
REVIEWER_SHA = "1ee55b22fe01512010baeeac4c49545d1690f7279144dc0b0e20353d56590d7b"
ROOT_CONTEXT = PKG / "preserved-root-context"


def pin(path: Path, record: dict) -> None:
    blob = path.read_bytes()
    assert len(blob) == record["bytes"] and hashlib.sha256(blob).hexdigest() == record["sha256"], path


def main() -> None:
    assert hashlib.sha256(REVIEWER.read_bytes()).hexdigest() == REVIEWER_SHA
    own = runpy.run_path(str(REVIEWER))
    parse = own["native_json"]
    manifest = parse(PKG / "prelaunch-manifest.json")
    approval = parse(PKG / "review/independent-prelaunch-go.json")
    preflight = parse(PKG / approval["preflight_relative_path"])
    closure = parse(RUN / "closure.json")
    failure = parse(RUN / "failure-seal.json")
    invocation = parse(RUN / "invocation.json")
    assert manifest["schema"] == "c09-var02-v107-prelaunch-manifest/v1"
    assert len(manifest["source_files"]) == manifest["source_count"] == 1726
    assert approval["schema"] == "c09-var02-v107-independent-prelaunch-go/v1"
    assert preflight["schema"] == "c09-var02-v107-ssh-preflight/v1"
    assert closure["schema"] == "c09-var02-v107-closure/v1"
    assert failure["schema"] == "c09-var02-v107-failure-seal/v1"
    assert invocation["schema"] == "c09-var02-v107-invocation/v1"
    assert closure["error"] == failure["error"] == "child OS exit=1"
    assert invocation["run_id"] == closure["run_id"] == failure["run_id"] == approval["run_id"]
    assert closure["approval_sha256"] == hashlib.sha256(
        (PKG / "review/independent-prelaunch-go.json").read_bytes()).hexdigest()
    assert closure["invocation_sha256"] == hashlib.sha256((RUN / "invocation.json").read_bytes()).hexdigest()
    assert closure["approved_preflight_sha256"] == approval["preflight_sha256"]
    assert closure["manifest_sha256"] == approval["manifest_sha256"]
    assert len(closure["raw"]) == 23
    for name, record in closure["raw"].items():
        pin(RUN / name, record)
    assert "invocation.json" not in closure["raw"]
    assert len(failure["files"]) == len(closure["raw"]) + 2
    for name, record in failure["files"].items():
        pin(RUN / name, record)
    assert "closure.json" in failure["files"] and "invocation.json" in failure["files"]

    source_map = {item["key"]: item["sha256"] for item in manifest["source_files"]}
    assert len(source_map) == 1726
    assert closure["source_hashes_before"] == closure["source_hashes_after"] == source_map
    assert invocation["source_hashes_before"] == preflight["source_hashes"] == source_map
    assert hashlib.sha256(json.dumps(source_map, separators=(",", ":")).encode()).hexdigest() == approval["source_map_sha256"]
    custody = parse(ROOT_CONTEXT / "actual-ssh5-helper-test-custody.json")
    helper_copies = {Path(record["original_path"]): record for record in custody["raw"]}
    contract = own["verify_parent_index"]()
    direct_tmp_names = {Path(record["path"]).name for record in own["direct_contract_pins"](contract)
                        if Path(record["path"]).parent.name == "tmp"}
    for item in manifest["source_files"]:
        original = Path(item["path"])
        if original.name == "publication-index-v1.json" and original.parent == PKG.parent:
            current = ROOT_CONTEXT / "publication-index-at-base.json"
        elif original.parent.name == "tmp" and original.name in direct_tmp_names:
            current = ROOT_CONTEXT / original.name
        elif item["key"].startswith("helper_test_original_raw:"):
            record = helper_copies[original]
            assert (record["bytes"], record["sha256"]) == (item["bytes"], item["sha256"])
            current = PKG / record["owned_copy_path"]
        else:
            current = original
        pin(current, item)

    steps = parse(RUN / "steps.json")
    assert [item["name"] for item in steps] == ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
    assert [item["status"] for item in steps] == ["completed"] * 5 + ["failed"]
    assert [item["exit_code"] for item in steps] == [0] * 5 + [1]
    assert all(type(item["exit_code"]) is int and type(item["child_session_id"]) is int and item["child_session_id"] == 0
               and type(item["child_pid"]) is int and item["child_pid"] > 0 and item["capture_error"] is None
               and item["gui_preserved"] is True for item in steps)
    assert parse(RUN / "roundtrip-validation.json")["passed"] is True
    assert parse(RUN / "author-validation.json") == {
        "schema": "c09-var02-v107-author-validation/v1", "passed": False, "error": "AssertionError: "}
    runlog = (RUN / "run.log").read_text(encoding="utf-8")
    assert "Input conversion completed. Errors: 0, Warnings: 3, Notes: 1" in runlog
    assert runlog.count("(warning #108)") == 1 and runlog.count("(warning #126)") == 2
    assert runlog.count("(notice #292)") == 1

    parent_source, parent_report, parent_trace = own["verified_parent"](contract)
    child_source = parse(RUN / "input.json")
    own["source_child"](parent_source, child_source, contract)
    own["roundtrip"](child_source, parse(RUN / "roundtrip-raw.json"))
    original_log = (RUN / "model.log").read_text(encoding="utf-8")
    printed = "return resource transport task 0 starts with 1 resources, transportation time: 0.5"
    assert original_log.count(printed) == 1
    original_parser_rejected = False
    try:
        own["trace"](original_log)
    except AssertionError:
        original_parser_rejected = True
    assert original_parser_rejected
    # Diagnostics only: replace the one printed *label* in memory, never a time,
    # line order, ID, station, quantity, source cell, or raw file.
    diagnostic_log = original_log.replace(printed, printed.replace("0.5", "0.125"))
    trace = own["trace"](diagnostic_log)
    own["validate_pair"](parent_trace, trace)
    assert trace["times"]["return_start"] == 9.46988
    assert trace["times"]["return_end"] == trace["times"]["home_pm"] == 9.59488
    assert trace["times"]["home_done"] == 9.84488
    actual_elapsed = trace["times"]["return_end"] - trace["times"]["return_start"]
    assert abs(actual_elapsed - .125) < 1e-9
    child_report = parse(RUN / "report-raw.json")
    expected_plan = own["report_plan"](child_source, trace)
    report_cells = own["compare_report"](child_report, parent_report, expected_plan)
    assert report_cells == 1754
    tampered = deepcopy(child_report)
    resource = next(table for table in tampered["report"]["tables"] if table["name"] == "ResourceResults")
    nrw = [column["name"] for column in resource["columns"]].index("NRW")
    resource["instances"][0]["rows"][18][nrw] += .00001
    report_mutation_rejected = False
    try:
        own["compare_report"](tampered, parent_report, expected_plan)
    except AssertionError:
        report_mutation_rejected = True
    assert report_mutation_rejected
    print(json.dumps({"decision": "NO_GO_RUN_DIAGNOSTIC", "run_id": RUN.name,
                      "contract_sha256": manifest["contract_sha256"],
                      "closure_sha256": hashlib.sha256((RUN / "closure.json").read_bytes()).hexdigest(),
                      "failure_sha256": hashlib.sha256((RUN / "failure-seal.json").read_bytes()).hexdigest(),
                      "manifest_source_records": 1726, "closure_raw_seals": 23,
                      "steps": [item["name"] + ":" + str(item["exit_code"]) for item in steps],
                      "printed_return_transportation_time_hours": .5,
                      "event_elapsed_return_hours": actual_elapsed,
                      "home_pm_start": trace["times"]["home_pm"],
                      "home_pm_end": trace["times"]["home_done"],
                      "diagnostic_in_memory_label_substitution": True,
                      "full_report_cells_reconciled_under_diagnostic_substitution": report_cells,
                      "changed_report_cell_rejected": report_mutation_rejected,
                      "original_reviewer_parser_rejected": original_parser_rejected,
                      "author_checker_passed": False}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
