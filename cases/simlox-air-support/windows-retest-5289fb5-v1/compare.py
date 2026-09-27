"""Read-only compare fresh PR22 Windows runs with frozen engine and native evidence.

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
MODES = {"ordinary": "ordinary-utf8-01", "crlf": "crlf-utf8-01", "lf": "lf-utf8-01"}
OLD_RECEIPT_SHA = "330c968bb26e7c6c1be83d3b3007221f05b32d09578634932e972b22718815c4"


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
        for index, row in enumerate(rows):
            item = observed["intervals"][index]
            require(item["index"] == index, f"{case}.intervals[{index}].index")
            for name, native_value, engine_value in (
                    ("start", row[names.index("STINT")] * 60, item["start_minutes"]),
                    ("end", row[names.index("ETINT")] * 60, item["end_minutes"])):
                require(abs(native_value - engine_value) <= 6e-7,
                        f"{case}.intervals[{index}].{name}", engine_value, native_value)
            for field in FIELDS:
                native_value = row[names.index(field)]
                engine_value = item[field]
                require(abs(native_value - engine_value) <= 1e-8,
                        f"{case}.intervals[{index}].{field}", engine_value, native_value)
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
                          "waves": wave_times})
    require(summaries[0]["waves"] == summaries[1]["waves"], f"{case}.native_replay")
    return summaries


def compare(native_repo: Path, engine_repo: Path, dispatch: Path):
    previous = native_repo / "cases/simlox-air-support/engine-return-review-c97b732-v1/receipt.json"
    require(sha(previous.read_bytes()) == OLD_RECEIPT_SHA, "historical_receipt_sha")
    manifest = read(native_repo / "cases/simlox-air-support/handoff-v1/manifest.json")
    require(subprocess.check_output(["git", "-C", str(engine_repo), "rev-parse", "HEAD"],
                                    text=True).strip() ==
            "5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe", "engine_revision")
    report = {"schema": "simlox-pr22-windows-independent-compare/v1",
              "historical_receipt_sha256": OLD_RECEIPT_SHA,
              "engine_head": "5289fb59c4f32887d8e535ccfa3e9ff00dbdecbe",
              "modes": {}}
    frozen_root = "experiments/simlox_pairing/evidence/v1"
    for mode, output_name in MODES.items():
        output = dispatch / "runs" / output_name
        source = read(output / "source-fingerprints.json")
        before = read(dispatch / ("ordinary-utf8-before.json" if mode == "ordinary"
                                  else f"{mode}-before.json"))["source_identity"]
        require(source["build_fingerprint"] == before["build_fingerprint"]
                == "8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1",
                f"{mode}.build_fingerprint")
        require(source["executed_source_fingerprint"] == before["executed_source_fingerprint"],
                f"{mode}.executed_source_fingerprint")
        require(len(source["source_files"]) == len(source["executed_source_files"]) == 26,
                f"{mode}.source_count")
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
                           "native_runs": runs, "first_discrepancy": None}
        negatives = read(output / "negative-controls.json")
        require(negatives["status"] == "passed" and len(negatives["controls"]) == 4
                and all(item["detected"] for item in negatives["controls"]),
                f"{mode}.four_negative_controls")
        report["modes"][mode] = {"output_directory": str(output),
                                  "source_build_fingerprint": source["build_fingerprint"],
                                  "executed_source_fingerprint": source["executed_source_fingerprint"],
                                  "consumer_source_fingerprint": source["consumer_source_fingerprint"],
                                  "cases": cases,
                                  "negative_controls": [x["control"] for x in negatives["controls"]],
                                  "output_file_sha256": {str(p.relative_to(output)).replace('\\', '/'):
                                                         sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}}
    report["status"] = "bounded_windows_pairing_verified_not_full_equivalence"
    report["first_discrepancy"] = None
    return report


def main() -> int:
    native_repo, engine_repo, dispatch, target = map(Path, sys.argv[1:5])
    require(not target.exists(), "output_must_be_new")
    try:
        result = compare(native_repo, engine_repo, dispatch)
        code = 0
    except Exception as error:
        result = {"schema": "simlox-pr22-windows-independent-compare/v1",
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
