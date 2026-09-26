"""Freeze compact A01/A02 review records from two immutable validated native runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SOURCE_SHA = "1b01a20111aed6c6fc96339c512147c862178967c01e67421eb380379b45f8d0"
SIMLOX_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
GENERATOR_AT_RUN_SHA = "34d0c0c66d13b3820c076ea8b5e60954d045dee40a41fe16f1046a69ba676a87"
VALIDATOR_AT_RUN_SHA = "d1b9d838cbcf5d264d0874e9c46496f9bd6c97481d786193392dcbbdada5399f"
CONTRACT_AT_RUN_SHA = {"A01": "e076f65e42798abd681f3d73a487fb903bd72bb0ddff99ddfe679dda092058ca",
                       "A02": "accce87ec239e143c0a42220048256a10f6e735dfaa0cabfbdc5aaa4c79b50f0"}
RUNS = {
    "A01": ("A01-single-aircraft-single-mission", "a01-final-20260927-01", "a01-replay-20260927-02"),
    "A02": ("A02-single-aircraft-repeated-missions", "a02-final-20260927-01", "a02-replay-20260927-02"),
}
SIGNATURE_KINDS = {"notification", "start", "success", "completion", "ready_decreased", "ready_increased"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: dict) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def file_index(run: Path) -> dict:
    return {path.name: {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(run.iterdir()) if path.is_file()}


def build(case_id: str) -> dict[str, dict]:
    folder, first_id, replay_id = RUNS[case_id]
    case = ROOT / folder
    first, replay = (REPO / "data/local/simlox-case-library/v1" / case_id / run_id for run_id in (first_id, replay_id))
    documents = [json.loads((run / "validation.json").read_text(encoding="utf-8-sig")) for run in (first, replay)]
    if any(doc["status"] != "cli_behavior_verified" or not doc["behavior"]["passed"] for doc in documents):
        raise ValueError("both runs must pass the native behavior validator")
    if any(doc["artifacts"]["input.json"]["sha256"] != sha256(case / "native-input.json") for doc in documents):
        raise ValueError("replays must use the checked native input")
    signatures = [[(event["kind"], event["time_hours_printed"], event["text"])
                   for event in doc["event_index"] if event["kind"] in SIGNATURE_KINDS] for doc in documents]
    if signatures[0] != signatures[1]:
        raise ValueError("independent native replay diverged")
    contract = json.loads((case / "contract.json").read_text(encoding="utf-8"))
    manifest = {
        "case_id": case_id, "version": contract["version"], "parent_case": contract["parent_case"],
        "delta": contract["delta"], "requires": contract["requires"],
        "source": {"main_commit": "595cb5eee9987324b19a8c3566f201f937e05f15",
                   "native_schema_from": "phase6/b-zero-stock-repair/b-zero-stock-repair.json (row-free table schema only)",
                   "native_schema_source_sha256": SOURCE_SHA,
                   "native_schema_sha256": sha256(ROOT / "native-schema.json")},
        "tool": {"simlox_version_from_prior_source_record": "2017.0.0.0",
                 "simlox_exe_sha256": SIMLOX_SHA,
                 "isolated_python_version": "3.12.14",
                 "isolated_python_exe_sha256": "2204195cec25879507d958a8b6949add67091244b8b4da9cf3672f993548fa49",
                 "generator_at_native_run_sha256": GENERATOR_AT_RUN_SHA,
                 "generator_current_sha256": sha256(ROOT / "tools/generate_native.py"),
                 "native_runner_sha256": sha256(ROOT / "tools/run_native.ps1"),
                 "validator_at_native_run_sha256": VALIDATOR_AT_RUN_SHA,
                 "validator_current_sha256": sha256(ROOT / "tools/validate_native.py")},
        "input": {"path": str((case / "native-input.json").resolve()),
                  "sha256": sha256(case / "native-input.json"),
                  "contract_at_native_run_sha256": CONTRACT_AT_RUN_SHA[case_id],
                  "contract_sha256": sha256(case / "contract.json"),
                  "parameters_sha256": sha256(case / "parameters.json")},
        "repetition_count": 1, "threads": 1, "observation_hours": [0, 36],
        "run_ids": [first_id, replay_id], "gui_status": "pending_private_handoff",
        "cross_engine_status": "unverified",
    }
    if case_id == "A02":
        manifest["parent_diff_sha256"] = sha256(case / "parent-diff.json")
    outcomes = [
        {"kind": event["kind"], "time_hours_printed": event["time_hours_printed"], "line": event["line"],
         "text": event["text"]}
        for event in documents[0]["event_index"] if event["kind"] in SIGNATURE_KINDS
    ]
    result = {
        "case_id": case_id, "version": contract["version"], "status": "cli_behavior_verified_gui_pending",
        "planned_schedule_hours": contract["mission"]["schedule_hours"],
        "first_run": documents[0]["behavior"], "replay_run": documents[1]["behavior"],
        "selected_event_timeline": outcomes,
        "event_replay_exact": True,
        "interpretation": "FTMO interval integral equals the full scheduled mission duration; ready count drops at notification, not takeoff. Zero-duration lifecycle log markers remain but NPSTA=0 without a MissionPreparation business row.",
        "output_limits": "MSTF/MSUF are aggregate fractions; single-repetition counts here are independently reconstructed from ENLOG. No full J35 equivalence or GUI acceptance."
    }
    index = {
        "case_id": case_id, "version": contract["version"],
        "retrieval_command": f"Get-ChildItem -Recurse -LiteralPath '{str((REPO / 'data/local/simlox-case-library/v1' / case_id).resolve())}'",
        "runs": [{"run_id": run.name, "directory": str(run.resolve()), "artifacts": file_index(run)} for run in (first, replay)],
        "first_run_selected_event_replay_equal": True,
        "source_history": "Initial zero-duration MissionPreparation-row runs and the A01 no-row diagnostic are retained separately under the same ignored v1 evidence tree.",
    }
    acceptance = {
        "case_id": case_id, "version": contract["version"],
        "cli_model_valid": True, "cli_behavior_verified": True,
        "gui_calibration": "pending", "gui_review": "pending", "reusable_publication": "provisional_not_accepted",
        "parent_gate": "A01 CLI behavior verified; A01 GUI publication pending" if case_id == "A02" else None,
        "independent_replay": "selected event signature and expected outputs match exactly",
        "observation_window": "normal 36 h path verified; A01 RCEND-only clipping verified; SIMPE near-return probes invalid #204, terminal cutoff unverified",
        "cross_engine_pairing": "unverified",
        "remaining": ["private GUI calibration/review screenshots", "independent AMD128 pairing run",
                      "native simulation-stop semantics for a mission crossing SIMPE"],
    }
    return {"manifest.json": manifest, "results-summary.json": result,
            "acceptance.json": acceptance, "evidence-index.json": index}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(RUNS), required=True)
    args = parser.parse_args()
    folder = ROOT / RUNS[args.case][0]
    records = build(args.case)
    for name in records:
        if (folder / name).exists():
            raise FileExistsError(folder / name)
    for name, value in records.items():
        write_new(folder / name, value)
    print(json.dumps({"case_id": args.case, "created": list(records)}))


if __name__ == "__main__":
    main()
