"""Stdlib-only A01/A02 handoff packer and portable contract validator.

`pack` is run in the source checkout. `verify` accepts only the archive and
does not import SIMLOX, use Windows paths, or claim engine conformance.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import zipfile

SOURCE_COMMIT = "04dce604f6be75df064d40519187b482ceb4ddb8"
INPUT_SHA = {
    "A01": "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7",
    "A02": "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8",
}
CONTRACT_SHA = {
    "A01": "29d81aeadc5b138b07a3e6242fec8df74a768998c71d3ee0e5e4ca0bf45c7cb6",
    "A02": "f192c22de44ec20cf8581e2652ce8b4a44fc315acb7998624be340cb5a42a465",
}
PAIRING_SHA = "5ccd4318ad03338c693bfff379c163d80a86b56c71a74d5c9095ad1e82e4677f"
WINDOW_SHA = "6013b78ebd9e53c3ee154cf4b1010572f6cb1679ca86e65e6fefa0b21182e03a"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
SEALED_TOOLS = {"generator": "98229746cd334c3431b47894866e189f7892c367edfc6cf98b0f8fa85b57765b",
                "validator": "43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354",
                "runner": "f685a71e8a59d97c71a37ced9799be502fe531d5c61c4f4f666614f1dca1e22e",
                "binding": "d7cb8cdb670d6ac24536254904d9ac527bee1cfa1d9954dca9bd6a7d9ca0c28a"}
CASE_RECORD_SHA = {
    "A01": {"manifest": "9b9018d65d43df3b5026cad8e1e713e7200f77c171b54b076891d0f08667620a",
            "evidence_index": "2fe2383e513b0e59c581d5e7b48ec8da000a674a9f41e257b0e4f91836deb880"},
    "A02": {"manifest": "c2db7928a5c67deb1ba2393daaa51fdcef7bd3636ed84e461bc5914751f348b8",
            "evidence_index": "b584816ca459c75bd5de160eb44b7b458c0dbe1b478c56142c44a3283732041d"},
}
CASE_DIR = {"A01": "A01-single-aircraft-single-mission",
            "A02": "A02-single-aircraft-repeated-missions"}
METRICS = ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")
RUN_IDS = {
    "A01": ("a01-bound-final-20260927-03", "a01-bound-replay-20260927-04"),
    "A02": ("a02-bound-final-20260927-03", "a02-bound-replay-20260927-04"),
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def must(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def interval_rows(contract: dict) -> list[dict]:
    hand = contract["hand_expected"]
    starts, ends = hand["actual_start_hours"], hand["actual_end_hours"]
    notices = hand["notification_hours"]
    must(contract["hours_to_minutes"] == 60 and contract["time_unit_native"] == "hour"
         and contract["time_unit_pairing"] == "minute", "invalid hour/minute units")
    must(contract["observation"]["end_hours"] == 36
         and contract["observation"]["interval_minutes"] == 30, "unexpected observation grid")
    must(len(starts) == len(ends) == len(notices) == hand["planned_waves"], "wave cardinality")
    rows = []
    for index in range(72):
        left, right = index / 2, (index + 1) / 2
        def overlap(windows: list[tuple[float, float]]) -> float:
            return sum(max(0.0, min(right, end) - max(left, start)) for start, end in windows) / .5
        flying = overlap(list(zip(starts, ends)))
        allocated = overlap(list(zip(notices, ends)))
        reserved = overlap(list(zip(notices, starts)))
        rows.append({"index": index, "start_hours": left, "end_hours": right,
                     "start_minutes": index * 30, "end_minutes": (index + 1) * 30,
                     "FTMO": flying, "NSYMO": flying, "NSYMA": allocated,
                     "NSYMR": reserved, "NSYRY": 1 - allocated})
    return rows


def event_rows(contract: dict) -> list[dict]:
    hand = contract["hand_expected"]
    sid = contract["aircraft"][0]["native_sid"]
    must(sid == "TEACH-AIR-01" and contract["aircraft"][0]["qtyps"] == 1,
         "wrong stable aircraft identity")
    must(contract["mission"]["business_id"] == "BASIC-MISSION", "wrong mission identity")
    aircraft = f"<{sid},0>"
    unit = "TEACH-UNIT"
    ready_body = f"{aircraft} nbr ready increased at unit: <{unit} at <BASE-01,0>>"
    events = [{"kind": "ready_increased", "time_hours": 0, "time_minutes": 0,
               "mission_instance": None, "aircraft_instance": aircraft,
               "native_body": ready_body, "mapping": "state_observable"}]
    for ordinal, (notice, start, end) in enumerate(zip(
            hand["notification_hours"], hand["actual_start_hours"], hand["actual_end_hours"])):
        tag = f"<BASIC-MISSION,{unit},0,0,{ordinal}>"
        unit_at_base = f"<{unit} at <BASE-01,0>>"
        stages = (
            ("notification", notice, f"<{unit}> mission ordered: BASIC-MISSION", "mission_observable"),
            ("created", notice, f"{tag} mission created:", "mapping_pending"),
            ("activated", notice, f"{tag} mission activated, systems requested: 1", "mapping_pending"),
            ("allocation", notice, f"{tag} mission allocates system: {aircraft}", "state_observable"),
            ("ready_decreased", notice, f"{aircraft} nbr ready decreased at unit: {unit_at_base}", "state_observable"),
            ("start", start, f"{tag} mission starting, duration: 2 : {aircraft}", "mission_observable"),
            ("task_start", start + .5, f"{tag} task starting: {aircraft}", "native_inner_task_mapping_pending"),
            ("task_completion", end - .5, f"{tag} task completed: {aircraft}", "native_inner_task_mapping_pending"),
            ("success", end, f"{tag} mission success:", "mission_observable"),
            ("completion", end, f"{tag} mission completed: {aircraft}", "mission_observable"),
            ("ready_increased", end, ready_body, "state_observable"),
        )
        for kind, hour, body, mapping in stages:
            events.append({"kind": kind, "time_hours": hour, "time_minutes": hour * 60,
                           "mission_instance": tag, "aircraft_instance": aircraft,
                           "native_body": body, "mapping": mapping})
    return events


def expected_case(contract: dict) -> dict:
    rows = interval_rows(contract)
    events = event_rows(contract)
    integrals = {metric: sum(row[metric] * .5 for row in rows) for metric in METRICS}
    hand = contract["hand_expected"]
    must(integrals["FTMO"] == hand["flight_hours_integral"]
         and integrals["NSYRY"] == hand["ready_hours_integral"], "declared integral mismatch")
    return {"case_id": contract["case_id"], "version": contract["version"],
            "aircraft_instance": "<TEACH-AIR-01,0>",
            "mission_instance_tags": [f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>"
                                      for i in range(hand["planned_waves"])],
            "events": events, "intervals": rows,
            "integrals": {"FTMO_hours": integrals["FTMO"],
                          "NSYMO_aircraft_hours": integrals["NSYMO"],
                          "NSYMA_aircraft_hours": integrals["NSYMA"],
                          "NSYMR_aircraft_hours": integrals["NSYMR"],
                          "NSYRY_aircraft_hours": integrals["NSYRY"]},
            "terminal": {key: hand[key] for key in ("planned_waves", "launched_waves", "sorties",
                       "completed_waves", "cancelled_waves", "unfinished_at_horizon")},
            "observation": {"simulation_period_hours": 36, "normal_collection_end_hours": 36,
                            "interval_minutes": 30}}


def window_summary(review: dict) -> list[dict]:
    result = []
    for run in review["runs"]:
        observed = run["observation"]
        result.append({"variant": run["variant"],
                       "requested_rcend_hours": observed["requested_observation_end_hours"],
                       "native_system_last_end_hours": observed["native_system_result_last_end_hours"],
                       "native_ftmo_integral_hours": observed["native_ftmo_interval_integral_hours"],
                       "native_result_summary_window_hours": observed["native_summary_window_hours"],
                       "native_result_summary_mstf_msuf": observed["native_summary_mstf_msuf"],
                       "notified_pending": observed["notified_pending_at_collection_end"],
                       "in_flight": observed["in_flight_at_collection_end"],
                       "completed": observed["completed_by_collection_end"],
                       "full_enlog_completion_hours": observed["completions_hours_printed"][0]})
    return result


def semantic_verify(manifest: dict, files: dict[str, bytes]) -> dict:
    must(manifest.get("task_id") == "simlox-a01-a02-gui-pairing-readiness-v1"
         and manifest.get("schema") == "simlox-a01-a02-portable-handoff-v1"
         and manifest.get("accepted_source_commit") == SOURCE_COMMIT, "wrong task/schema/source commit")
    must(manifest.get("engine_status") == "not_run_unverified"
         and manifest.get("gui_status") == "pending_private_user_handoff"
         and manifest.get("engine_mapping_status") == "pending_unverified"
         and manifest.get("native_observation_status") == "four_sealed_cli_normal_replay_runs_verified_on_4700-3",
         "acceptance status promoted")
    must(manifest.get("units") == {"native_time": "hour", "pairing_time": "minute",
                                        "hours_to_minutes": 60, "FTMO_integral": "hour",
                                        "NSY_integral": "aircraft-hour"}, "wrong units")
    must(manifest.get("tolerances") == {"event_time_hours": .0001,
              "event_time_minutes": .006,
              "normal_interval_endpoint_hours": 1e-8,
              "normal_interval_endpoint_minutes": 6e-7,
              "rcend_requested_to_native_float_hours": 2e-7,
              "profile_value": 1e-8, "integral": 1e-8,
              "profile_value_units": "FTMO mission-operation hours/hour; NSY* aircraft count",
              "integral_units": "FTMO hours; NSY* aircraft-hours",
              "discrete_counts_and_identities": "exact"}, "wrong tolerances")
    must(manifest.get("case_versions") == {"A01": "1.0.0", "A02": "1.0.0"}, "case versions changed")
    must(manifest.get("sealed_tools_sha256") == SEALED_TOOLS, "sealed tool fingerprints changed")
    native_tool = manifest.get("native_executable", {})
    must(native_tool.get("sha256") == EXE_SHA
         and native_tool.get("product_version_raw") == "2017.0.0.0"
         and native_tool.get("version_provenance", "").startswith("4700-3 Get-Item"),
         "native executable identity/version changed")
    must(manifest.get("normal_observation") == {"SIMPE_hours": 36, "RCEND_hours": 36,
         "system_intervals": 72, "result_summary_window_hours": [0, 36]}, "normal window changed")
    expected = json.loads(files["expected-observations.json"])
    must(expected.get("schema") == "a01-a02-expected-observations-v1", "expected schema")
    must(len(expected.get("cases", {})) == 2, "missing case expectation")
    for case_id in CASE_DIR:
        input_path = f"cases/{case_id}/native-input.json"
        contract_path = f"cases/{case_id}/contract.json"
        must(digest(files[input_path]) == INPUT_SHA[case_id]
             and digest(files[contract_path]) == CONTRACT_SHA[case_id], "wrong input/contract source hash")
        contract = json.loads(files[contract_path])
        must(expected["cases"][case_id] == expected_case(contract), f"{case_id} event/state profile mismatch")
        case_manifest = json.loads(files[f"cases/{case_id}/manifest.json"])
        must(digest(files[f"cases/{case_id}/manifest.json"]) == CASE_RECORD_SHA[case_id]["manifest"]
             and digest(files[f"cases/{case_id}/evidence-index.json"]) == CASE_RECORD_SHA[case_id]["evidence_index"],
             "accepted record source hash changed")
        must(case_manifest["run_ids"] == list(RUN_IDS[case_id])
             and case_manifest["input"]["sha256"] == INPUT_SHA[case_id]
             and len(case_manifest["run_bindings"]) == 2, "accepted run lineage mismatch")
        must(case_manifest["tool"]["simlox_exe_sha256"] == EXE_SHA
             and {"generator": case_manifest["tool"]["generator_at_native_run_sha256"],
                  "validator": case_manifest["tool"]["validator_at_native_run_sha256"],
                  "runner": case_manifest["tool"]["native_runner_sha256"],
                  "binding": case_manifest["tool"]["binding_tool_sha256"]} == SEALED_TOOLS,
             "accepted case tool lineage changed")
        must(manifest["cases"][case_id]["run_ids"] == list(RUN_IDS[case_id]), "handoff run IDs changed")
        must(manifest["cases"][case_id]["input_sha256"] == INPUT_SHA[case_id]
             and manifest["cases"][case_id]["contract_sha256"] == CONTRACT_SHA[case_id]
             and manifest["cases"][case_id]["aircraft_instance"] == expected["cases"][case_id]["aircraft_instance"]
             and manifest["cases"][case_id]["mission_tags"] == expected["cases"][case_id]["mission_instance_tags"],
             "handoff case identity/fingerprint changed")
        index = json.loads(files[f"cases/{case_id}/evidence-index.json"])
        runs = manifest.get("native_runs", {}).get(case_id, [])
        must(len(runs) == 2, "missing bound native replay")
        for ordinal, (run, binding, indexed) in enumerate(zip(runs, case_manifest["run_bindings"], index["runs"])):
            must(run["run_id"] == indexed["run_id"] == case_manifest["run_ids"][ordinal]
                 and run["invocation_id"] == binding["invocation_id"], "native run identity mismatch")
            for name, record in run["original_artifacts"].items():
                must(record["sha256"] == indexed["artifacts"][name]["sha256"]
                     and record["bytes"] == indexed["artifacts"][name]["bytes"],
                     "native original evidence fingerprint mismatch")
    must(digest(files["pairing-contract.json"]) == PAIRING_SHA, "pairing contract source hash")
    must(digest(files["collection-window-review-v2.json"]) == WINDOW_SHA, "window review source hash")
    must(manifest.get("source_fingerprints") == {
        "pairing_contract_sha256": PAIRING_SHA,
        "collection_window_review_sha256": WINDOW_SHA,
        "expected_observations_sha256": digest(files["expected-observations.json"])},
        "handoff source/expected fingerprint mismatch")
    review = json.loads(files["collection-window-review-v2.json"])
    must(expected["rcend_collection"] == window_summary(review), "collection mapping changed")
    must(expected["simpe_input_validity"] == {
        "rejected_error_204_hours": [7.5, 9, 9.9999, 10, 10.0001],
        "positive_control_hours": [10.5, 12],
        "classification": "sampled_native_input_validity_only_no_stop_or_cancellation_rule"},
        "wrong SIMPE cutoff classification")
    expected_windows = [(7.5, 1, 0, 0), (9, 0, 1, 0), (9.9999, 0, 1, 0),
                        (10, 0, 0, 1), (10.0001, 0, 0, 1)]
    for row, (end, pending, flying, complete) in zip(expected["rcend_collection"], expected_windows):
        must(row["requested_rcend_hours"] == end
             and (row["notified_pending"], row["in_flight"], row["completed"]) == (pending, flying, complete)
             and row["native_result_summary_window_hours"] == [0, 36]
             and row["full_enlog_completion_hours"] == 10, "RCEND/summary/event classification changed")
        must(abs(row["native_system_last_end_hours"] - end) <= 2e-7,
             "native float RCEND endpoint outside declared observation precision")
    must(expected["rcend_collection"][1]["native_result_summary_mstf_msuf"] == [1, 1]
         and expected["rcend_collection"][1]["in_flight"] == 1,
         "9h MSUF counterexample lost")
    report = json.loads(files["consumer-report-template.json"])
    must(report["engine_status"] == "not_run" and report["equivalence_status"] == "unverified"
         and all(item["status"] == "not_run" for item in report["cases"].values()),
         "engine result falsely accepted")
    gui = json.loads(files["gui-checklist.json"])
    must(gui["status"] == "pending_private_user_handoff", "GUI status falsely accepted")
    for case_id in CASE_DIR:
        final_artifacts = manifest["native_runs"][case_id][0]["original_artifacts"]
        must(gui["cases"][case_id]["sxi_sha256"] == final_artifacts["model.sxi"]["sha256"]
             and gui["cases"][case_id]["sxo_sha256"] == final_artifacts["model.sxo"]["sha256"],
             "GUI retained model fingerprint mismatch")
    return {"case_count": 2, "intervals_per_case": 72,
            "engine_status": "not_run_unverified", "gui_status": "pending_private_user_handoff"}


def verify_package(path: Path, manifest_sha256: str | None = None) -> dict:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        must(len(names) == len(set(names)), "duplicate package member")
        must(all(not PurePosixPath(name).is_absolute() and ".." not in PurePosixPath(name).parts
                 and not name.endswith("/") for name in names), "unsafe package member")
        must("manifest.json" in names, "missing manifest")
        raw_manifest = archive.read("manifest.json")
        if manifest_sha256:
            must(digest(raw_manifest) == manifest_sha256, "manifest SHA mismatch")
        manifest = json.loads(raw_manifest)
        payload = manifest.get("payload_files", {})
        must(set(names) == set(payload) | {"manifest.json"}, "missing/extra package file")
        files = {name: archive.read(name) for name in payload}
        for name, info in payload.items():
            must(digest(files[name]) == info["sha256"] and len(files[name]) == info["bytes"],
                 f"payload hash/size mismatch: {name}")
        details = semantic_verify(manifest, files)
    return {"status": "portable_integrity_and_contract_verified_not_engine_equivalence",
            "zip_sha256": digest(path.read_bytes()), "manifest_sha256": digest(raw_manifest), **details}


def pack(repo: Path, output: Path) -> dict:
    handoff = repo / "cases/simlox-air-support/handoff-v1"
    manifest_path = handoff / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    must(not output.exists(), "immutable output archive already exists")
    payload = manifest["payload_files"]
    files = {}
    for archive_path, info in payload.items():
        source = repo / info["repo_relative_path"]
        raw = source.read_bytes()
        must(digest(raw) == info["sha256"] and len(raw) == info["bytes"],
             f"source changed before packaging: {archive_path}")
        files[archive_path] = raw
    semantic_verify(manifest, files)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted({"manifest.json": manifest_path.read_bytes(), **files}.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return verify_package(output, digest(manifest_path.read_bytes()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    package = sub.add_parser("pack")
    package.add_argument("--repo", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--zip", type=Path, required=True)
    verify.add_argument("--manifest-sha256")
    args = parser.parse_args()
    result = pack(args.repo, args.output) if args.command == "pack" else verify_package(args.zip, args.manifest_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
