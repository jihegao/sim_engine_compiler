"""Freeze the handoff on 4700-3 from accepted sealed runs, read-only.

Only expected-observations.json and manifest.json in this handoff directory
are created. Raw native models, logs, reports and earlier validation are never
written. This script is not needed by a portable consumer.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
LIB = HERE.parent
REPO = HERE.parents[2]
sys.path.insert(0, str(LIB / "tools"))
from validate_native import remove_trailing_commas, table_rows, validate  # noqa: E402
from portable import (CASE_DIR, CONTRACT_SHA, INPUT_SHA, METRICS, PAIRING_SHA,
                      RUN_IDS, SOURCE_COMMIT, WINDOW_SHA, digest, encoded,
                      expected_case, must, window_summary)  # noqa: E402

RAW_ROOT = REPO / "data/local/simlox-case-library/v1"
PAYLOAD_SOURCES = {
    "pairing-contract.json": "cases/simlox-air-support/pairing-contract.json",
    "collection-window-review-v2.json": "cases/simlox-air-support/collection-window-review-v2.json",
    "expected-observations.json": "cases/simlox-air-support/handoff-v1/expected-observations.json",
    "gui-checklist.json": "cases/simlox-air-support/handoff-v1/gui-checklist.json",
    "consumer-report-template.json": "cases/simlox-air-support/handoff-v1/consumer-report-template.json",
    "README.md": "cases/simlox-air-support/handoff-v1/README.md",
    "portable.py": "cases/simlox-air-support/handoff-v1/portable.py",
}
for case, folder in CASE_DIR.items():
    for name in ("contract.json", "parameters.json", "native-input.json", "manifest.json",
                 "acceptance.json", "results-summary.json", "evidence-index.json", "mapping.csv"):
        PAYLOAD_SOURCES[f"cases/{case}/{name}"] = f"cases/simlox-air-support/{folder}/{name}"


def check_native(case_id: str, expected: dict) -> list[dict]:
    accepted = []
    for run_id in RUN_IDS[case_id]:
        run = RAW_ROOT / case_id / run_id
        result = validate(run, case_id, write=False, require_binding=True)
        must(result["status"] == "cli_behavior_verified" and result["behavior"]["passed"],
             f"native strict validation failed: {run_id}")
        actual_events = result["event_index"]
        relevant = {item["kind"] for item in expected["events"]}
        observed = [event for event in actual_events if event["kind"] in relevant]
        must(len(observed) == len(expected["events"]), f"event cardinality mismatch: {run_id}")
        for frozen, actual in zip(expected["events"], observed):
            must(frozen["kind"] == actual["kind"]
                 and frozen["native_body"] == actual["body"]
                 and abs(frozen["time_hours"] - float(actual["time_hours_printed"])) <= .0001,
                 f"event mismatch: {run_id} {frozen['kind']}")
        raw_report = (run / "report-raw.json").read_bytes()
        report = json.loads(remove_trailing_commas(raw_report))
        native_rows = table_rows(report, "SystemResults")
        must(len(native_rows) == 72, f"not 72 native intervals: {run_id}")
        for frozen, actual in zip(expected["intervals"], native_rows):
            must(abs(frozen["start_hours"] - actual["STINT"]) <= 1e-8
                 and abs(frozen["end_hours"] - actual["ETINT"]) <= 1e-8,
                 f"native interval endpoint mismatch: {run_id} {frozen['index']}")
            for metric in METRICS:
                must(abs(frozen[metric] - actual[metric]) <= 1e-8,
                     f"native state profile mismatch: {run_id} {frozen['index']} {metric}")
        must(result["behavior"]["system_interval_integrals_aircraft_hours"]["NSYRY"]
             == expected["integrals"]["NSYRY_aircraft_hours"], "native ready integral mismatch")
        index = json.loads((LIB / CASE_DIR[case_id] / "evidence-index.json").read_bytes())
        entry = next(item for item in index["runs"] if item["run_id"] == run_id)
        artifacts = {name: {"sha256": entry["artifacts"][name]["sha256"],
                            "bytes": entry["artifacts"][name]["bytes"]}
                     for name in ("invocation.json", "closure.json", "input.json", "model.sxi",
                                  "model.sxo", "report-raw.json", "model.log", "validation.json")}
        for name, info in artifacts.items():
            path = run / name
            must(digest(path.read_bytes()) == info["sha256"] and path.stat().st_size == info["bytes"],
                 f"original evidence changed: {run_id}/{name}")
        accepted.append({"run_id": run_id, "original_directory_windows": str(run.resolve()),
                         "invocation_id": result["binding"]["invocation_id"],
                         "original_artifacts": artifacts,
                         "recheck_command_windows":
                         "& 'C:\\Users\\user\\Documents\\Codex\\2026-09-26\\simlox-j35-event-parity\\workspace\\evidence\\py312-venv\\Scripts\\python.exe' "
                         f"'cases/simlox-air-support/tools/validate_native.py' --case {case_id} "
                         f"--run-dir '{run.resolve()}' --read-only"})
    return accepted


def freeze() -> dict:
    must(digest((LIB / "pairing-contract.json").read_bytes()) == PAIRING_SHA,
         "accepted pairing contract changed")
    review_path = LIB / "collection-window-review-v2.json"
    must(digest(review_path.read_bytes()) == WINDOW_SHA, "accepted window review changed")
    review = json.loads(review_path.read_bytes())
    cases = {}
    native_runs = {}
    for case_id, folder in CASE_DIR.items():
        contract_file = LIB / folder / "contract.json"
        input_file = LIB / folder / "native-input.json"
        must(digest(contract_file.read_bytes()) == CONTRACT_SHA[case_id]
             and digest(input_file.read_bytes()) == INPUT_SHA[case_id], "accepted input/contract changed")
        contract = json.loads(contract_file.read_bytes())
        cases[case_id] = expected_case(contract)
        native_runs[case_id] = check_native(case_id, cases[case_id])
    expected = {"schema": "a01-a02-expected-observations-v1", "cases": cases,
                "rcend_collection": window_summary(review),
                "simpe_input_validity": {
                    "rejected_error_204_hours": [7.5, 9, 9.9999, 10, 10.0001],
                    "positive_control_hours": [10.5, 12],
                    "classification": "sampled_native_input_validity_only_no_stop_or_cancellation_rule"}}
    expected_path = HERE / "expected-observations.json"
    must(not expected_path.exists(), "expected file already frozen")
    expected_path.write_bytes(encoded(expected))
    payload = {}
    for archive_path, relative in sorted(PAYLOAD_SOURCES.items()):
        source = REPO / relative
        raw = source.read_bytes()
        payload[archive_path] = {"repo_relative_path": relative,
                                 "sha256": digest(raw), "bytes": len(raw)}
    tool = json.loads((LIB / CASE_DIR["A01"] / "manifest.json").read_bytes())["tool"]
    manifest = {
        "schema": "simlox-a01-a02-portable-handoff-v1",
        "task_id": "simlox-a01-a02-gui-pairing-readiness-v1",
        "accepted_source_commit": SOURCE_COMMIT,
        "accepted_draft_pr": 21,
        "case_versions": {"A01": "1.0.0", "A02": "1.0.0"},
        "cases": {case: {"input_sha256": INPUT_SHA[case], "contract_sha256": CONTRACT_SHA[case],
                          "run_ids": list(RUN_IDS[case]), "mission_tags": cases[case]["mission_instance_tags"],
                          "aircraft_instance": cases[case]["aircraft_instance"]} for case in CASE_DIR},
        "source_fingerprints": {"pairing_contract_sha256": PAIRING_SHA,
                                "collection_window_review_sha256": WINDOW_SHA,
                                "expected_observations_sha256": digest(expected_path.read_bytes())},
        "native_executable": {"path_windows": r"C:\Program Files\Systecon\SIMLOX\Simlox.exe",
                              "sha256": tool["simlox_exe_sha256"],
                              "product_version_raw": "2017.0.0.0",
                              "file_version_raw": "0.0.0.0",
                              "display_file_version": None,
                              "version_provenance": "4700-3 Get-Item Simlox.exe VersionInfo read-only; GUI About not observed"},
        "sealed_tools_sha256": {"generator": tool["generator_at_native_run_sha256"],
                                "validator": tool["validator_at_native_run_sha256"],
                                "runner": tool["native_runner_sha256"],
                                "binding": tool["binding_tool_sha256"]},
        "native_runs": native_runs,
        "units": {"native_time": "hour", "pairing_time": "minute", "hours_to_minutes": 60,
                  "FTMO_integral": "hour", "NSY_integral": "aircraft-hour"},
        "tolerances": {"event_time_hours": .0001,
                       "event_time_minutes": .006,
                       "normal_interval_endpoint_hours": 1e-8,
                       "normal_interval_endpoint_minutes": 6e-7,
                       "rcend_requested_to_native_float_hours": 2e-7,
                       "profile_value": 1e-8, "integral": 1e-8,
                       "profile_value_units": "FTMO mission-operation hours/hour; NSY* aircraft count",
                       "integral_units": "FTMO hours; NSY* aircraft-hours",
                       "discrete_counts_and_identities": "exact"},
        "normal_observation": {"SIMPE_hours": 36, "RCEND_hours": 36,
                               "system_intervals": 72, "result_summary_window_hours": [0, 36]},
        "output_boundaries": {
            "native_report_fields": ["ResultSummary.MSTF", "ResultSummary.MSUF", "SystemResults.FTMO",
                                     "SystemResults.NSYMO", "SystemResults.NSYMA", "SystemResults.NSYMR",
                                     "SystemResults.NSYRY"],
            "not_comparable_without_mapping": ["MSTF/MSUF as completed-by-RCEND counts",
                 "native task_start/task_completion as engine mission start/end",
                 "SIMPE #204 threshold as dynamic cancellation/deadline rule",
                 "same integer seed as same RNG stream", "zero mechanism counters as resource/stock/PM/CM/fault acceptance"],
            "rcend_9h_counterexample": "MSUF=1 with mission still in flight; full ENLOG completes at 10h"},
        "gui_status": "pending_private_user_handoff",
        "gui_action": "Windows App > Devices > 4700-3; user privately connects, then inspect retained SXI/SXO without recalculation",
        "gui_first_order": "not_achieved_cli_preceded_gui",
        "native_observation_status": "four_sealed_cli_normal_replay_runs_verified_on_4700-3",
        "engine_mapping_status": "pending_unverified",
        "engine_status": "not_run_unverified",
        "next_engine_gate": "independent AMD128 run with build/input/Plan fingerprints, stable identity and event mapping, 72 intervals, terminal counts and first discrepancy",
        "reproduce_input_command_template": "python cases/simlox-air-support/tools/generate_native.py --case {A01|A02} --output <fresh-path>; compare SHA256 to case input hash",
        "payload_files": payload,
    }
    manifest_path = HERE / "manifest.json"
    must(not manifest_path.exists(), "manifest already frozen")
    manifest_path.write_bytes(encoded(manifest))
    return {"expected_sha256": digest(expected_path.read_bytes()),
            "manifest_sha256": digest(manifest_path.read_bytes()),
            "strict_native_run_count": sum(map(len, native_runs.values()))}


if __name__ == "__main__":
    print(json.dumps(freeze(), ensure_ascii=False, indent=2))
