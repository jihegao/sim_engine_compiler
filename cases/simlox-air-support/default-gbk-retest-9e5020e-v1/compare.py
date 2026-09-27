"""Read-only compare fresh default-GBK runs with frozen engine and native evidence.

Usage: python compare.py NATIVE_REPO PR22_CHECKOUT DISPATCH OUTPUT_JSON
Does not start SIMLOX or use native expected observations to produce engine output.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

FIELDS = ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")
MODES = {"normal": "normal-01", "crlf": "crlf-01", "lf": "lf-01"}
OLD_RECEIPT_SHA = "08b2f20cbbc520561e8edc27fa48567e70d2160d77da554c4fd8d8410666e147"
NATIVE_MANIFEST_SHA = "0b7294414c5cafa050cf90349659822f5d08ff2b42421359826a26759483d987"
OLD_5289_MANIFEST_SHA = "64b5b8acefae3ec62a67a8700ce670e19ebef52542fcce9eac156fb96a275c73"
CONSUMER_PIN_SHA = "9ede7b36554d3dc3894917852c74a8c5dad759139fe6574b9bed701fd2cf5f79"
CASE_ARTIFACTS = (
    "business-ir.json", "canonical-input.json", "comparison.json", "core-ir.json",
    "engine-result.json", "execution-plan.json", "lineage.json",
    "observations.json", "source-mapping.json",
)
TOP_ARTIFACTS = ("consumer-report.json", "handoff-verification.json",
                 "negative-controls.json", "source-fingerprints.json")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> str:
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def git_json(repo: Path, name: str):
    raw = subprocess.check_output(["git", "-C", str(repo), "show", "HEAD:" + name])
    return json.loads(raw.decode("utf-8"))


def require(ok: bool, path: str, actual=None, expected=None):
    if not ok:
        raise AssertionError(f"{path}: actual={actual!r}, expected={expected!r}")


def verify_output_index(output: Path, mode: str) -> set[str]:
    """Require the complete 24-payload/one-index schema and exact raw bytes."""
    index = read(output / "evidence-index.json")
    require(len(index["files"]) == 24, f"{mode}.indexed_payload_count",
            len(index["files"]), 24)
    found_json = {str(path.relative_to(output)).replace("\\", "/")
                  for path in output.rglob("*.json")}
    indexed_paths = {name.replace("\\", "/") for name in index["files"]}
    expected_paths = {f"{case}/{name}" for case in ("A01", "A02")
                      for name in ("artifact-fingerprints.json", *CASE_ARTIFACTS)}
    expected_paths |= set(TOP_ARTIFACTS)
    require(len(indexed_paths) == 24 and indexed_paths == expected_paths,
            f"{mode}.exact_index_membership", indexed_paths, expected_paths)
    require(found_json == indexed_paths | {"evidence-index.json"},
            f"{mode}.json_membership", found_json, indexed_paths)
    for name, expected_hash in index["files"].items():
        normalized = name.replace("\\", "/")
        require(normalized in expected_paths and ".." not in normalized.split("/")
                and not normalized.startswith("/") and ":" not in normalized,
                f"{mode}.safe_index_path.{name}")
        require(sha((output / normalized).read_bytes()) == expected_hash,
                f"{mode}.index_sha256.{name}")
    for case in ("A01", "A02"):
        folder = output / case
        products = read(folder / "artifact-fingerprints.json")
        require(set(products) == set(CASE_ARTIFACTS),
                f"{mode}.{case}.artifact_fingerprint_membership")
        for name, expected_hash in products.items():
            require(sha((folder / name).read_bytes()) == expected_hash,
                    f"{mode}.{case}.artifact_fingerprint_sha256.{name}")
    return found_json


def native_lines(path: Path):
    result = []
    for number, body in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.match(r"^Time: ([0-9.]+) (.*)$", body)
        if match:
            result.append((number, float(match.group(1)), match.group(2)))
    return result


def event(log, body: str):
    found = [(line, hour) for line, hour, text in log if text == body]
    require(len(found) == 1, "native_event_count:" + body, len(found), 1)
    return found[0]


def mapped(observed, kind: str, tag: str | None, aircraft: str, minute: float):
    found = [x for x in observed["mapped_events"] if x["kind"] == kind
             and x["mission_instance"] == tag and x["aircraft_instance"] == aircraft]
    require(len(found) == 1, f"mapped_event_count:{kind}:{tag}", len(found), 1)
    require(abs(found[0]["time_minutes"] - minute) <= .006,
            f"mapped_event_time:{kind}:{tag}", found[0]["time_minutes"], minute)


def native_case(case: str, native_repo: Path, manifest: dict, observed: dict) -> list[dict]:
    aircraft = "<TEACH-AIR-01,0>"
    tags = manifest["cases"][case]["mission_tags"]
    require(observed["identity_mapping"]["aircraft"] == {"TEACH-AIR-01": aircraft},
            f"{case}.aircraft_mapping")
    require(set(observed["identity_mapping"]["missions"].values()) == set(tags),
            f"{case}.mission_identity_set")
    summaries = []
    for record in manifest["native_runs"][case]:
        folder = Path(record["original_directory_windows"])
        require(folder.is_dir(), f"{case}.native_dir")
        for name, spec in record["original_artifacts"].items():
            raw = (folder / name).read_bytes()
            require(len(raw) == spec["bytes"] and sha(raw) == spec["sha256"],
                    f"{case}.{record['run_id']}.{name}.sha256")
        validation = read(folder / "validation.json")
        require(validation["status"] == "cli_behavior_verified", f"{case}.native_valid")
        normalized = folder / "report-normalized.json"
        require(sha(normalized.read_bytes()) == validation["normalized_report"]["sha256"],
                f"{case}.normalized_report_sha")
        report = read(normalized)["report"]
        table = next(x for x in report["tables"] if x["name"] == "SystemResults")
        names = [x["name"] for x in table["columns"]]
        rows = table["instances"][0]["rows"]
        require(len(rows) == len(observed["intervals"]) == 72, f"{case}.interval_count")
        native_integrals = {field: 0.0 for field in FIELDS}
        for index, row in enumerate(rows):
            item = observed["intervals"][index]
            duration_hours = row[names.index("ETINT")] - row[names.index("STINT")]
            require(item["index"] == index, f"{case}.intervals[{index}].index")
            for name, native_value, engine_value in (
                    ("start", row[names.index("STINT")] * 60, item["start_minutes"]),
                    ("end", row[names.index("ETINT")] * 60, item["end_minutes"])):
                require(abs(native_value - engine_value) <= 6e-7,
                        f"{case}.intervals[{index}].{name}", engine_value, native_value)
            for field in FIELDS:
                native_value = row[names.index(field)]
                engine_value = item[field]
                native_integrals[field] += native_value * duration_hours
                require(abs(native_value - engine_value) <= 1e-8,
                        f"{case}.intervals[{index}].{field}", engine_value, native_value)
        scale = 1 if case == "A01" else 3
        expected_integrals = {"FTMO": 2 * scale, "NSYMO": 2 * scale,
                              "NSYMA": 3 * scale, "NSYMR": scale,
                              "NSYRY": 33 if case == "A01" else 27}
        for field, expected in expected_integrals.items():
            require(abs(native_integrals[field] - expected) <= 2e-5,
                    f"{case}.native_integral.{field}", native_integrals[field], expected)
        require(observed["integrals"] == {
            "FTMO_hours": 2 * scale, "NSYMO_aircraft_hours": 2 * scale,
            "NSYMA_aircraft_hours": 3 * scale, "NSYMR_aircraft_hours": scale,
            "NSYRY_aircraft_hours": expected_integrals["NSYRY"]},
            f"{case}.engine_integrals")
        terminal_expected = {"planned_waves": scale, "launched_waves": scale,
                             "completed_waves": scale, "sorties": scale,
                             "cancelled_waves": 0, "unfinished_at_horizon": 0}
        require(observed["terminal"] == terminal_expected,
                f"{case}.engine_terminal_counts", observed["terminal"], terminal_expected)
        log = native_lines(folder / "model.log")
        orders = [(line, hour) for line, hour, text in log if text ==
                  "<TEACH-UNIT> mission ordered: BASIC-MISSION"]
        ready_up = [(line, hour) for line, hour, text in log if text ==
                    f"{aircraft} nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>"]
        ready_down = [(line, hour) for line, hour, text in log if text ==
                      f"{aircraft} nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>"]
        require(len(orders) == len(ready_down) == len(tags), f"{case}.native_notice_count")
        require(len(ready_up) == len(tags) + 1 and ready_up[0][1] == 0,
                f"{case}.native_ready_restoration")
        mapped(observed, "ready_increased", None, aircraft, 0)
        wave_times = []
        for index, tag in enumerate(tags):
            created = event(log, f"{tag} mission created: ")
            activated = event(log, f"{tag} mission activated, systems requested: 1")
            allocation = event(log, f"{tag} mission allocates system: {aircraft}")
            start = event(log, f"{tag} mission starting, duration: 2 : {aircraft}")
            success = event(log, f"{tag} mission success: ")
            completion = event(log, f"{tag} mission completed: {aircraft}")
            notice = orders[index]
            require(notice[0] < created[0] < activated[0] < allocation[0],
                    f"{case}.native_notice_order")
            require(notice[1] == created[1] == activated[1] == allocation[1]
                    == ready_down[index][1], f"{case}.native_allocation_time")
            require(success[1] == completion[1] == ready_up[index + 1][1],
                    f"{case}.native_completion_time")
            for kind, occurrence in (
                    ("notification", notice), ("allocation", allocation),
                    ("ready_decreased", ready_down[index]), ("start", start),
                    ("success", success), ("completion", completion),
                    ("ready_increased", ready_up[index + 1])):
                mapped(observed, kind, tag, aircraft, occurrence[1] * 60)
            wave_times.append({"mission": tag, "notice_hour": notice[1],
                               "start_hour": start[1], "completion_hour": completion[1]})
        summaries.append({"run_id": record["run_id"], "report_sha256":
                          record["original_artifacts"]["report-raw.json"]["sha256"],
                          "log_sha256": record["original_artifacts"]["model.log"]["sha256"],
                          "native_rows_compared": 72, "profile_fields_compared": 5,
                          "native_integrals": native_integrals,
                          "engine_terminal_counts": observed["terminal"],
                          "waves": wave_times})
    require(summaries[0]["waves"] == summaries[1]["waves"], f"{case}.native_replay")
    return summaries


def compare(native_repo: Path, engine_repo: Path, dispatch: Path):
    previous = native_repo / "cases/simlox-air-support/windows-retest-5289fb5-v1/receipt.json"
    require(sha(previous.read_bytes()) == OLD_RECEIPT_SHA, "historical_receipt_sha")
    manifest_path = native_repo / "cases/simlox-air-support/handoff-v1/manifest.json"
    require(sha(manifest_path.read_bytes()) == NATIVE_MANIFEST_SHA,
            "native_manifest_external_sha256", sha(manifest_path.read_bytes()),
            NATIVE_MANIFEST_SHA)
    manifest = read(manifest_path)
    require(subprocess.check_output(["git", "-C", str(engine_repo), "rev-parse", "HEAD"],
                                    text=True).strip() ==
            "9e5020eeb0ea29a7e442a991e9f559b7e209d676", "engine_revision")
    report = {"schema": "simlox-pr22-default-gbk-independent-compare/v1",
              "historical_receipt_sha256": OLD_RECEIPT_SHA,
              "native_manifest_external_sha256": NATIVE_MANIFEST_SHA,
              "engine_head": "9e5020eeb0ea29a7e442a991e9f559b7e209d676",
              "modes": {}}
    pins_path = dispatch / "coordinator-consumer-byte-pins.json"
    pins_raw = pins_path.read_bytes()
    require(sha(pins_raw) == CONSUMER_PIN_SHA, "coordinator_consumer_pin_sha256")
    pins = json.loads(pins_raw.decode("utf-8"))
    require(pins["source_commit"] == report["engine_head"], "consumer_pin_revision")
    report["coordinator_consumer_pin_sha256"] = sha(pins_raw)
    old_dispatch = dispatch.parent / "simlox-pr22-windows-retest-5289fb5-v1"
    old_manifest_path = old_dispatch / "raw-artifact-manifest-v3.json"
    require(sha(old_manifest_path.read_bytes()) == OLD_5289_MANIFEST_SHA,
            "historical_5289_raw_manifest_sha")
    old_files = {item["relative_path"]: item for item in read(old_manifest_path)["items"]}
    report["historical_5289_raw_manifest_sha256"] = OLD_5289_MANIFEST_SHA
    frozen_root = "experiments/simlox_pairing/evidence/v1"
    for mode, output_name in MODES.items():
        output = dispatch / "runs" / output_name
        source = read(output / "source-fingerprints.json")
        snapshot = read(dispatch / f"{mode}-before-tests.json")
        after = read(dispatch / f"{mode}-after-run.json")
        require(snapshot["utf8_mode"] == after["utf8_mode"] == 0,
                f"{mode}.outer_utf8_mode")
        require(snapshot["locale_encoding"].lower() in ("cp936", "gbk", "936")
                and after["locale_encoding"].lower() in ("cp936", "gbk", "936"),
                f"{mode}.outer_default_locale")
        require(snapshot["environment_selectors"] == after["environment_selectors"]
                == {"PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONUTF8": None, "PYTHONIOENCODING": None},
                f"{mode}.outer_environment")
        before = snapshot["source_identity"]
        require(before == after["source_identity"], f"{mode}.source_before_after")
        pin_files = pins["lf_files" if mode == "lf" else "strict_crlf_files"]
        pin_fingerprint = pins["lf_fingerprint" if mode == "lf" else
                               "strict_whole_file_crlf_fingerprint"]
        require(len(pin_files) == 7 and before["consumer_source_files"] == pin_files,
                f"{mode}.consumer_actual_bytes_vs_independent_pins")
        require(before["consumer_source_fingerprint"] == pin_fingerprint,
                f"{mode}.consumer_actual_fingerprint_vs_independent_pin")
        require(source["consumer_source_files"] == pin_files and
                source["consumer_source_fingerprint"] == pin_fingerprint,
                f"{mode}.run_consumer_bytes_vs_independent_pins")
        require(source["build_fingerprint"] == before["build_fingerprint"]
                == "8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1",
                f"{mode}.build_fingerprint")
        require(source["executed_source_fingerprint"] == before["executed_source_fingerprint"],
                f"{mode}.executed_source_fingerprint")
        require(len(source["source_files"]) == len(source["executed_source_files"]) == 26,
                f"{mode}.source_count")
        probe = read(dispatch / f"{mode}-env-probe.stdout")
        require(probe["utf8_mode"] == 0 and probe["locale_encoding"].lower()
                in ("cp936", "gbk", "936"), f"{mode}.child_default_locale")
        require(probe["python"] == "3.12.14" and probe["simpy"] == "4.1.1" and
                probe["environment_selectors"] == snapshot["environment_selectors"] and
                probe["imported_runtime_file"] == snapshot["imported_runtime_file"],
                f"{mode}.child_versions_import_environment")
        tests_record = read(dispatch / f"{mode}-tests.json")
        tests = read(dispatch / f"{mode}-tests.stdout")
        run_record = read(dispatch / f"{mode}-run.json")
        require(tests_record["exit_code"] == run_record["exit_code"] == 0 and
                tests["collected"] == tests["executed"] == 35 and
                tests["skipped"] == tests["failures"] == tests["errors"] == 0 and
                tests["status"] == "passed", f"{mode}.outer_35_tests")
        for label, command in (("tests", tests_record), ("run", run_record)):
            require(command["environment_selectors"] == snapshot["environment_selectors"] and
                    command["parent_python_utf8_mode"] == 0 and
                    command["parent_locale_encoding"].lower() in ("cp936", "gbk", "936") and
                    command["source_identity_before"] == before ==
                    command["source_identity_after"] and
                    command["source_identity_unchanged"] and
                    command["git_status_after"] == "" and
                    "-X" not in command["command"], f"{mode}.{label}.outer_process_and_bytes")
        found_json = verify_output_index(output, mode)
        cases = {}
        for case in ("A01", "A02"):
            folder = output / case
            produced = read(folder / "engine-result.json")
            observed = read(folder / "observations.json")
            plan = read(folder / "execution-plan.json")
            lineage = read(folder / "lineage.json")
            canonical_input = read(folder / "canonical-input.json")
            frozen_result = git_json(engine_repo, f"{frozen_root}/{case}/engine-result.json")
            frozen_plan = git_json(engine_repo, f"{frozen_root}/{case}/execution-plan.json")
            frozen_canonical = git_json(engine_repo, f"{frozen_root}/{case}/canonical-input.json")
            for name in CASE_ARTIFACTS:
                require(read(folder / name) ==
                        git_json(engine_repo, f"{frozen_root}/{case}/{name}"),
                        f"{mode}.{case}.frozen_json.{name}")
                old_relative = f"runs/ordinary-utf8-01/{case}/{name}"
                old_raw = (old_dispatch / old_relative).read_bytes()
                require(old_relative in old_files and
                        sha(old_raw) == old_files[old_relative]["sha256"] and
                        len(old_raw) == old_files[old_relative]["bytes"],
                        f"{mode}.{case}.historical_5289_byte_pin.{name}")
                require(json.loads(old_raw.decode("utf-8")) == read(folder / name),
                        f"{mode}.{case}.historical_5289_json.{name}")
            require(produced == frozen_result, f"{mode}.{case}.raw_engine_result")
            require(plan == frozen_plan, f"{mode}.{case}.plan")
            require(canonical_input == frozen_canonical, f"{mode}.{case}.canonical_input")
            require(canonical(produced) == observed["bindings"]["result_sha256"],
                    f"{mode}.{case}.result_observation_digest")
            require(produced["plan_fingerprint"] == lineage["plan_fingerprint"]
                    == observed["bindings"]["plan_fingerprint"], f"{mode}.{case}.plan_binding")
            require(canonical(canonical_input) == plan["source_inputs_sha256"]
                    == lineage["canonical_sha256"], f"{mode}.{case}.canonical_plan_binding")
            comparison = read(folder / "comparison.json")
            require(comparison["status"] == "matched" and comparison["failed_count"] == 0
                    and comparison["first_divergence"] is None, f"{mode}.{case}.comparison")
            require(comparison["check_count"] == (625 if case == "A01" else 681),
                    f"{mode}.{case}.check_count")
            runs = native_case(case, native_repo, manifest, observed)
            cases[case] = {"canonical_digest": canonical(canonical_input),
                           "plan_fingerprint": lineage["plan_fingerprint"],
                           "raw_result_semantic_digest": canonical(produced),
                           "raw_result_file_sha256": sha((folder / "engine-result.json").read_bytes()),
                           "observation_file_sha256": sha((folder / "observations.json").read_bytes()),
                           "check_count": comparison["check_count"],
                           "interval_count": len(observed["intervals"]),
                           "native_runs": runs, "frozen_json_objects_compared": 9,
                           "historical_5289_json_objects_compared": 9,
                           "first_discrepancy": None}
        negatives = read(output / "negative-controls.json")
        require(negatives["status"] == "passed" and len(negatives["controls"]) == 4
                and all(item["detected"] for item in negatives["controls"]),
                f"{mode}.four_negative_controls")
        report["modes"][mode] = {"output_directory": str(output),
                                  "outer_utf8_mode": 0,
                                  "outer_locale_encoding": snapshot["locale_encoding"],
                                  "indexed_json_payloads": 24,
                                  "total_json_files": len(found_json),
                                  "outer_tests": {"collected": 35, "executed": 35,
                                                  "skipped": 0, "errors": 0,
                                                  "failures": 0},
                                  "source_build_fingerprint": source["build_fingerprint"],
                                  "executed_source_fingerprint": source["executed_source_fingerprint"],
                                  "consumer_source_fingerprint": source["consumer_source_fingerprint"],
                                  "cases": cases,
                                  "negative_controls": [x["control"] for x in negatives["controls"]],
                                  "output_file_sha256": {str(p.relative_to(output)).replace('\\', '/'):
                                                         sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}}
    report["status"] = "bounded_default_gbk_pairing_verified_not_full_equivalence"
    report["first_discrepancy"] = None
    return report


def main() -> int:
    native_repo, engine_repo, dispatch, target = map(Path, sys.argv[1:5])
    require(not target.exists(), "output_must_be_new")
    try:
        result = compare(native_repo, engine_repo, dispatch)
        code = 0
    except Exception as error:
        result = {"schema": "simlox-pr22-default-gbk-independent-compare/v1",
                  "status": "failed", "first_discrepancy": str(error),
                  "error_type": type(error).__name__}
        code = 1
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "first_discrepancy": result["first_discrepancy"],
                      "output": str(target)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
