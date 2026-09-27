"""Read-only A01/A02 native/engine evidence check; Python standard library only.

Usage: python recheck.py NATIVE_REPO PR22_SOURCE ORIGINAL_ZIP REBUILT_ZIP
The script does not execute either simulation engine or change its evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

FIELDS = ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")
ARTIFACTS = {
    "invocation.json", "closure.json", "input.json", "model.sxi", "model.sxo",
    "report-raw.json", "model.log", "validation.json",
}
ORIGINAL_ZIP_SHA = "fe5555954cc6596b478346a6df1ff1e3c78da9d01f16c9f73ce967407a9c0ece"
REBUILT_ZIP_SHA = "4f78ba072f5b458231ba8ba394e25bc9fc953e2bf288f28e30682a4e7a5a3a60"
MANIFEST_SHA = "0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987"
ENGINE_INDEX_SHA = "ae06705d168458f6899232350760bbc32732656b06f9216dc59abe84c542ce31"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_blob(root: Path, path: Path) -> bytes:
    """Read committed PR22 bytes; Windows checkout CRLF must not change evidence."""
    return subprocess.check_output(["git", "-C", str(root), "show",
                                    "HEAD:" + path.relative_to(root).as_posix()])


def engine_sha(root: Path, path: Path) -> str:
    return hashlib.sha256(git_blob(root, path)).hexdigest()


def engine_read(root: Path, path: Path):
    return json.loads(git_blob(root, path).decode("utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def compressed(raw: bytes, info: zipfile.ZipInfo) -> bytes:
    offset = info.header_offset
    require(raw[offset:offset + 4] == b"PK\x03\x04", "invalid ZIP local header")
    name_len, extra_len = struct.unpack_from("<HH", raw, offset + 26)
    start = offset + 30 + name_len + extra_len
    return raw[start:start + info.compress_size]


def check_zip(original: Path, rebuilt: Path) -> dict:
    require(sha(original) == ORIGINAL_ZIP_SHA, "delivered ZIP hash")
    require(sha(rebuilt) == REBUILT_ZIP_SHA, "PR22 ZIP hash")
    a, b = original.read_bytes(), rebuilt.read_bytes()
    require(len(a) == len(b) == 48491, "ZIP length")
    with zipfile.ZipFile(original) as za, zipfile.ZipFile(rebuilt) as zb:
        ai, bi = za.infolist(), zb.infolist()
        require(len(ai) == len(bi) == 24, "ZIP member count")
        require([x.filename for x in ai] == [x.filename for x in bi], "ZIP member/order")
        require(hashlib.sha256(za.read("manifest.json")).hexdigest() == MANIFEST_SHA,
                "external manifest")
        for x, y in zip(ai, bi):
            require(za.read(x) == zb.read(y), f"payload differs: {x.filename}")
            require(compressed(a, x) == compressed(b, y),
                    f"compressed payload differs: {x.filename}")
        # ZIP central-directory 'version made by' byte 1 is create_system.
        def central_offsets(raw: bytes) -> list[int]:
            return [i + 5 for i in range(len(raw) - 4) if raw[i:i + 4] == b"PK\x01\x02"]
        offsets = central_offsets(a)
        require(offsets == central_offsets(b) and len(offsets) == 24,
                "central directory structure")
        differing = [i for i, (left, right) in enumerate(zip(a, b)) if left != right]
        require(differing == offsets, "ZIP difference extends beyond create_system")
        require(all((a[i], b[i]) == (0, 3) for i in offsets), "ZIP OS marker")
    return {"members": 24, "compressed_payloads_identical": True,
            "only_create_system_bytes_differ": True, "differing_bytes": len(offsets)}


def lines(path: Path) -> list[tuple[int, float, str]]:
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.match(r"^Time: ([0-9.]+) (.*)$", line)
        if match:
            found.append((number, float(match.group(1)), match.group(2)))
    return found


def one_event(log, body: str) -> tuple[int, float]:
    matches = [(number, hour) for number, hour, text in log if text == body]
    require(len(matches) == 1, f"native event count {len(matches)}: {body}")
    return matches[0]


def trace_event(trace, kind: str, mission: str, aircraft: str):
    events = []
    for event in trace:
        if event["kind"] != kind:
            continue
        details = event.get("details", {})
        if kind == "operations_phase_created":
            if (details.get("mission_id") == mission and details.get("tail_number") == aircraft
                    and details.get("operations_phase") in {"preflight", "relaunch"}):
                events.append(event)
        elif kind == "mission_returned":
            if details.get("mission_id") == mission and event.get("entity") == aircraft:
                events.append(event)
        elif event.get("entity") == mission:
            events.append(event)
    require(len(events) == 1, f"engine event count {len(events)}: {kind} {mission}")
    return events[0]


def check_case(case: str, native_root: Path, engine_root: Path, manifest: dict,
               expected: dict, engine_index: dict) -> dict:
    evidence = engine_root / "experiments/simlox_pairing/evidence/v1"
    case_dir = evidence / case
    for name, digest in engine_index["files"].items():
        require(engine_sha(engine_root, evidence / name) == digest,
                f"engine evidence hash: {name}")
    engine_files = engine_read(engine_root, case_dir / "artifact-fingerprints.json")
    for name, digest in engine_files.items():
        require(engine_sha(engine_root, case_dir / name) == digest,
                f"engine case file hash: {case}/{name}")
    source = engine_read(engine_root, case_dir / "source-mapping.json")
    lineage = engine_read(engine_root, case_dir / "lineage.json")
    canonical = engine_read(engine_root, case_dir / "canonical-input.json")
    plan = engine_read(engine_root, case_dir / "execution-plan.json")
    result = engine_read(engine_root, case_dir / "engine-result.json")
    observed = engine_read(engine_root, case_dir / "observations.json")
    canonical_digest = hashlib.sha256(json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    require(canonical_digest == plan["source_inputs_sha256"] == lineage["canonical_sha256"]
            == observed["bindings"]["source_inputs_sha256"], "canonical/Plan binding")
    require(result["plan_fingerprint"] == lineage["plan_fingerprint"]
            == observed["bindings"]["plan_fingerprint"], "result/Plan binding")
    result_digest = hashlib.sha256(json.dumps(
        result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    require(result_digest == observed["bindings"]["result_sha256"],
            "raw engine result/observation binding")
    require(result["metrics"]["elapsed_minutes"] == result["time"] == 2160,
            "engine horizon")
    require(result["stop_reason"] == "duration", "engine stop reason")
    require(source["aircraft"]["canonical_tail_number"] == "TEACH-AIR-01"
            and source["aircraft"]["native_instance"] == "<TEACH-AIR-01,0>",
            "aircraft identity")
    require(len(source["missions"]) == (1 if case == "A01" else 3), "mission count")
    require(source["missions"][-1]["engine_mission_id"].endswith("-d2-w1")
            if case == "A02" else True, "A02 day-2 identity")

    normal_runs = []
    for record in manifest["native_runs"][case]:
        require(set(record["original_artifacts"]) == ARTIFACTS, "native artifact keys")
        folder = Path(record["original_directory_windows"])
        require(folder.is_dir(), f"missing native run {folder}")
        for name, spec in record["original_artifacts"].items():
            path = folder / name
            require(path.stat().st_size == spec["bytes"] and sha(path) == spec["sha256"],
                    f"native artifact hash: {record['run_id']}/{name}")
        require(sha(folder / "input.json") == manifest["cases"][case]["input_sha256"],
                "fixed native case input")
        invocation, closure = read(folder / "invocation.json"), read(folder / "closure.json")
        require(invocation["invocation_id"] == closure["invocation_id"]
                == record["invocation_id"], "native invocation identity")
        require(closure["invocation_sha256"] == sha(folder / "invocation.json"),
                "native invocation/closure binding")
        validation = read(folder / "validation.json")
        normalized = validation["normalized_report"]
        require(sha(folder / "report-normalized.json") == normalized["sha256"],
                "native normalized report hash")
        require(validation["status"] == "cli_behavior_verified",
                "native validation status")
        report = read(folder / "report-normalized.json")["report"]
        table = next(t for t in report["tables"] if t["name"] == "SystemResults")
        cols = [c["name"] for c in table["columns"]]
        rows = table["instances"][0]["rows"]
        require(len(rows) == 72, "native 72 intervals")
        log = lines(folder / "model.log")
        aircraft = "<TEACH-AIR-01,0>"
        native_events = []
        ready_up = [(line, hour) for line, hour, body in log if body ==
                    f"{aircraft} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>"]
        orders = [(line, hour) for line, hour, body in log if body ==
                  "<TEACH-UNIT> mission ordered: BASIC-MISSION"]
        require(len(ready_up) == len(source["missions"]) + 1, "native ready restoration")
        require(len(orders) == len(source["missions"]), "native notification count")
        require(ready_up[0][1] == 0, "native initial ready")
        wave_events = []
        for i, mapping in enumerate(source["missions"]):
            tag = mapping["native_mission_instance"]
            engine_id = mapping["engine_mission_id"]
            created = one_event(log, f"{tag} mission created: ")
            activation = one_event(log, f"{tag} mission activated, systems requested: 1")
            allocation = one_event(log, f"{tag} mission allocates system: {aircraft}")
            decrease = [(line, hour) for line, hour, body in log if body ==
                        f"{aircraft} nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>"]
            require(len(decrease) == len(source["missions"]), "native ready loss count")
            start = one_event(log, f"{tag} mission starting, duration: 2 : {aircraft}")
            success = one_event(log, f"{tag} mission success: ")
            complete = one_event(log, f"{tag} mission completed: {aircraft}")
            inner_start = one_event(log, f"{tag} task starting: {aircraft}")
            inner_end = one_event(log, f"{tag} task completed: {aircraft}")
            require(orders[i][1] == created[1] == activation[1] == allocation[1]
                    == decrease[i][1],
                    "native notice/allocation/ready-loss time")
            require(orders[i][0] < created[0] < activation[0] < allocation[0],
                    "native notification/creation/activation/allocation order")
            require(success[1] == complete[1] == ready_up[i + 1][1],
                    "native completion/ready-restoration time")
            eng_allocation = trace_event(result["trace"], "operations_phase_created",
                                         engine_id, "TEACH-AIR-01")
            eng_notice = trace_event(result["trace"], "preflight_created",
                                     engine_id, "TEACH-AIR-01")
            eng_start = trace_event(result["trace"], "mission_launched",
                                    engine_id, "TEACH-AIR-01")
            eng_return = trace_event(result["trace"], "mission_returned",
                                     engine_id, "TEACH-AIR-01")
            eng_success = trace_event(result["trace"], "mission_success_point_succeeded",
                                      engine_id, "TEACH-AIR-01")
            for label, native, engine in (("allocation", allocation, eng_allocation),
                                          ("notification_proxy", orders[i], eng_notice),
                                          ("start", start, eng_start),
                                          ("completion", complete, eng_return),
                                          ("success", success, eng_success)):
                require(abs(native[1] * 60 - engine["time"]) <= .006,
                        f"{case} {tag} {label} time")
            require(eng_start["details"]["aircraft"] == ["TEACH-AIR-01"],
                    "engine launch aircraft identity")
            require(inner_start[1] == start[1] + .5
                    and inner_end[1] == complete[1] - .5, "native-only inner task")
            native_events.append({"mission": tag, "engine_mission": engine_id,
                                  "notice_hour": orders[i][1], "created_hour": created[1],
                                  "activated_hour": activation[1],
                                  "allocation_hour": allocation[1],
                                  "start_hour": start[1], "success_hour": success[1],
                                  "completion_hour": complete[1], "inner_task_hours":
                                  [inner_start[1], inner_end[1]], "log_lines": {
                                      "ordered": orders[i][0], "created": created[0],
                                      "activated": activation[0], "allocation": allocation[0],
                                      "start": start[0], "success": success[0],
                                      "completion": complete[0]}})
            wave_events.append((allocation[1], start[1], complete[1]))
        require(len(observed["intervals"]) == 72
                and len(expected["cases"][case]["intervals"]) == 72, "72-bin evidence")
        integrals = {field: 0.0 for field in FIELDS}
        for i, row in enumerate(rows):
            start_hour, end_hour = i * .5, (i + 1) * .5
            observed_bin = observed["intervals"][i]
            require(observed_bin["index"] == i
                    and observed_bin["start_minutes"] == i * 30
                    and observed_bin["end_minutes"] == (i + 1) * 30,
                    f"engine interval index/endpoints {case} {i}")
            profile = {field: 0.0 for field in FIELDS}
            profile["NSYRY"] = 1.0
            for reserve, launch, complete in wave_events:
                if reserve <= start_hour < complete:
                    profile["NSYRY"] = 0.0
                    profile["NSYMA"] = 1.0
                    profile["NSYMR"] = float(start_hour < launch)
                    profile["NSYMO"] = float(start_hour >= launch)
                    profile["FTMO"] = profile["NSYMO"]
            require(abs(row[cols.index("STINT")] - start_hour) <= 1e-8
                    and abs(row[cols.index("ETINT")] - end_hour) <= 1e-8,
                    f"native interval endpoint {case} {i}")
            for field in FIELDS:
                actual = row[cols.index(field)]
                engine = observed_bin[field]
                frozen = expected["cases"][case]["intervals"][i][field]
                require(abs(actual - profile[field]) <= 1e-8
                        and abs(engine - actual) <= 1e-8
                        and abs(frozen - actual) <= 1e-8,
                        f"{case} interval[{i}].{field}: {actual}/{engine}/{frozen}")
                integrals[field] += actual * .5
        for field, value in integrals.items():
            suffix = "hours" if field == "FTMO" else "aircraft_hours"
            require(abs(value - observed["integrals"][f"{field}_{suffix}"]) <= 1e-8,
                    f"{case} integral {field}")
        metrics = result["metrics"]
        n = len(wave_events)
        require(metrics["planned_mission_waves"] == metrics["launched_sorties"]
                == metrics["completed_sorties"] == metrics["successful_mission_waves"] == n,
                "engine terminal counts")
        require(metrics["cancelled_sorties"] == 0 and
                all(m["status"] == "completed" and m["succeeded"] for m in
                    result["terminal_state"]["missions"]), "engine terminal state")
        require(observed["terminal"] == expected["cases"][case]["terminal"],
                "mapped terminal counts")
        normal_runs.append({"run_id": record["run_id"],
                            "input_sha256": sha(folder / "input.json"),
                            "sxi_sha256": sha(folder / "model.sxi"),
                            "sxo_sha256": sha(folder / "model.sxo"),
                            "log_sha256": sha(folder / "model.log"),
                            "report_sha256": sha(folder / "report-raw.json"),
                            "validation_sha256": sha(folder / "validation.json"),
                            "events": native_events, "bins_checked": 72, "integrals": integrals})
    require(normal_runs[0]["events"] == normal_runs[1]["events"], "native replay events")
    return {"native_input_sha256": manifest["cases"][case]["input_sha256"],
            "native_contract_sha256": manifest["cases"][case]["contract_sha256"],
            "canonical_file_sha256": engine_sha(engine_root, case_dir / "canonical-input.json"),
            "plan_fingerprint": lineage["plan_fingerprint"],
            "plan_file_sha256": engine_sha(engine_root, case_dir / "execution-plan.json"),
            "canonical_sha256": lineage["canonical_sha256"],
            "engine_result_file_sha256": engine_sha(engine_root, case_dir / "engine-result.json"),
            "engine_result_json_sha256": result_digest,
            "engine_observations_file_sha256": engine_sha(engine_root,
                                                           case_dir / "observations.json"),
            "native_runs": normal_runs, "mapped_first_discrepancy": None}


def check_source_identity(engine_root: Path, evidence: Path) -> dict:
    source = engine_read(engine_root, evidence / "source-fingerprints.json")
    head = subprocess.check_output(["git", "-C", str(engine_root), "rev-parse", "HEAD"],
                                   text=True).strip()
    require(head == "c97b73241ef961b99c2c416488bdd6462ce0e1d2", "PR22 head")
    for group in ("source_files", "consumer_source_files"):
        for name, digest in source[group].items():
            raw = subprocess.check_output(["git", "-C", str(engine_root),
                                           "show", "HEAD:" + name])
            require(hashlib.sha256(raw).hexdigest() == digest,
                    f"Git blob/source fingerprint {name}")
    require(source["commit"] == "595cb5eee9987324b19a8c3566f201f937e05f15",
            "engine build baseline")
    return {"pr22_head": head, "engine_build_baseline": source["commit"],
            "engine_build_fingerprint": source["build_fingerprint"],
            "consumer_source_fingerprint": source["consumer_source_fingerprint"],
            "source_git_blobs_checked": len(source["source_files"]),
            "consumer_git_blobs_checked": len(source["consumer_source_files"])}


def check_controls(evidence: Path, native_case: dict) -> list[dict]:
    engine_root = evidence.parents[3]
    controls = engine_read(engine_root, evidence / "negative-controls.json")["controls"]
    require([item["control"] for item in controls] == [
        "same_totals_wrong_schedule", "same_times_wrong_identity",
        "result_plan_mismatch", "canonical_input_plan_mismatch"], "control membership")
    shift, identity, result_plan, canonical_plan = controls
    require(all(item["detected"] for item in controls), "negative control detection")
    require(shift["same_integrals"] and shift["same_terminal_counts"],
            "shift preserves cumulative totals")
    require(shift["changed_canonical"]["mission_profile"]["composite_tasks"][0]
            ["taskItems"][0]["firstWaveTime"] == "08:30", "shift input")
    require(shift["changed_plan"]["missions"][0]["preparation_start"] == 450,
            "shift Plan")
    shifted_mission = native_case["native_runs"][0]["events"][0]["engine_mission"]
    shifted_trace = shift["actual_engine_result"]["trace"]
    require(trace_event(shifted_trace, "operations_phase_created", shifted_mission,
                        "TEACH-AIR-01")["time"] == 450 and
            trace_event(shifted_trace, "mission_launched", shifted_mission,
                        "TEACH-AIR-01")["time"] == 510,
            "shifted runtime trace")
    require(shift["first_discrepancy"]["path"] == "mapped_events[1].time_minutes"
            and shift["first_discrepancy"]["actual"] == 450
            and shift["first_discrepancy"]["expected"] == 420,
            "shift first event discrepancy")
    require(shift["first_interval_discrepancy"]["path"] == "intervals[14].NSYMA"
            and shift["first_interval_discrepancy"]["actual"] == 0
            and shift["first_interval_discrepancy"]["expected"] == 1,
            "shift first state-bin discrepancy")
    require(native_case["native_runs"][0]["events"][0]["notice_hour"] == 7,
            "shift native source notice")
    require(identity["first_discrepancy"]["path"] ==
            "mapped_events[0].aircraft_instance" and
            identity["first_discrepancy"]["actual"] == "<WRONG-AIRCRAFT,0>" and
            identity["first_discrepancy"]["expected"] == "<TEACH-AIR-01,0>",
            "wrong identity first discrepancy")
    require(result_plan["first_discrepancy"] ==
            {"code": "result_plan_mismatch", "path": "result.plan_fingerprint"},
            "result/Plan rejection")
    require(canonical_plan["first_discrepancy"]["path"] ==
            "bindings.source_inputs_sha256" and
            canonical_plan["first_discrepancy"]["expected"] == "0" * 64,
            "canonical/Plan rejection")
    return [{"name": item["control"], "detected": item["detected"],
             "first_discrepancy": item["first_discrepancy"],
             **({"first_interval_discrepancy": item["first_interval_discrepancy"]}
                if "first_interval_discrepancy" in item else {})} for item in controls]


def main() -> None:
    native_root, engine_root, original, rebuilt = map(Path, sys.argv[1:5])
    manifest = read(native_root / "cases/simlox-air-support/handoff-v1/manifest.json")
    expected = read(native_root / "cases/simlox-air-support/handoff-v1/expected-observations.json")
    evidence = engine_root / "experiments/simlox_pairing/evidence/v1"
    index = engine_read(engine_root, evidence / "evidence-index.json")
    require(manifest["accepted_source_commit"] == "04dce604f6be75df064d40519187b482ceb4ddb8",
            "native source")
    require(sha(native_root / "cases/simlox-air-support/handoff-v1/manifest.json") == MANIFEST_SHA,
            "native handoff manifest")
    payload = manifest["payload_files"]["expected-observations.json"]
    expected_path = native_root / "cases/simlox-air-support/handoff-v1/expected-observations.json"
    require(sha(expected_path) == payload["sha256"]
            and expected_path.stat().st_size == payload["bytes"],
            "manifest-pinned expected observations")
    require(engine_sha(engine_root, evidence / "evidence-index.json") == ENGINE_INDEX_SHA,
            "externally pinned engine evidence index")
    require(len(index["files"]) == 24, "engine evidence index membership")
    native_executable = manifest["native_executable"]
    require(sha(Path(native_executable["path_windows"])) == native_executable["sha256"],
            "native executable hash")
    receipt = {"schema": "a01-a02-engine-return-independent-recheck/v1",
               "native_handoff_source": "519b2094c3be355399bc101cdcfe30d456cbb47b",
               "accepted_native_source": manifest["accepted_source_commit"],
               "native_executable": native_executable,
               "native_manifest_sha256": MANIFEST_SHA,
               "engine_evidence_index_sha256": ENGINE_INDEX_SHA,
               "zip_transport": check_zip(original, rebuilt),
               "source_identity": check_source_identity(engine_root, evidence),
               "cases": {case: check_case(case, native_root, engine_root, manifest,
                                           expected, index) for case in ("A01", "A02")},
               "status": "matched_bounded_mapped_observables_only",
               "paired_runtime": "independent_python_reference",
               "notification_mapping": "preflight_created_commission_time_proxy_only",
               "gui_status": "pending_private_user_handoff",
               "full_equivalence_verified": False,
               "native_or_engine_executed_by_this_checker": False,
               "unaccepted_semantics": ["native_creation_activation", "native_inner_task",
                                        "same_tick_priority", "faults", "pm_cm", "resources",
                                        "stock_spares", "cancellation", "shared_rng",
                                        "A03", "J35_F35", "performance"]}
    receipt["negative_controls"] = check_controls(evidence, receipt["cases"]["A01"])
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
