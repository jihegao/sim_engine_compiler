"""Execute and archive the bounded A01/A02 pairing without native SIMLOX."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from experiments.simlox_pairing.canonical import compile_case
from experiments.simlox_pairing.negative_controls import run_controls
from experiments.simlox_pairing.observations import (
    compare_observations,
    extract_engine_observations,
)
from experiments.simlox_pairing.provenance import (
    DEFAULT_ARCHIVE,
    json_digest,
    load_handoff,
    sha256,
    source_identity,
)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True,
                               allow_nan=False) + "\n", encoding="utf-8")


def execute_pairing(output: Path, archive: Path = DEFAULT_ARCHIVE) -> dict:
    """Fresh output only; native expectations never enter compilation/execution."""
    if output.exists():
        raise ValueError("output already exists; use a fresh evidence directory")
    handoff = load_handoff(archive)
    source = source_identity()
    report = copy.deepcopy(handoff["report_template"])
    report["task_id"] = "engine-a01-a02-pairing-519b209-v1"
    report["engine_status"] = "independently_executed"
    report["handoff_verification"] = handoff["verification"]
    report["engine_identity_required"] = {
        "commit": source["commit"],
        "build_fingerprint": source["build_fingerprint"],
        "checkout_head": source["checkout_head"],
        "executed_source_fingerprint": source["executed_source_fingerprint"],
        "declared_modified_baseline_source_files": source[
            "declared_modified_baseline_source_files"
        ],
        "input_fingerprint": {},
        "execution_plan_fingerprint": {},
        "observation_level": "full",
    }
    report["mapping_required"] = {
        "aircraft_business_to_engine_id": {},
        "mission_instance_to_engine_id": {},
        "native_event_to_engine_event": {
            "notification": "preflight_created commission-time proxy; not a captured notification",
            "allocation": "operations_phase_created preflight/relaunch aircraft-to-mission binding",
            "ready_decreased": "same binding transition: not globally available",
            "start": "mission_launched",
            "completion": "mission_returned with validated completed terminal mission",
            "ready_increased": "initial available state or return plus zero-work postflight",
        },
        "native_interval_metric_to_engine_metric": {
            "FTMO": "trace-derived flying exposure",
            "NSYMO": "trace-derived flying count",
            "NSYMA": "trace-derived reserved plus flying count",
            "NSYMR": "trace-derived reserved-not-flying count",
            "NSYRY": "trace-derived globally available count; mission_ready is excluded",
        },
        "unmapped_events_or_metrics": [
            "independent native notification/creation/activation mechanism and microstep order",
            "native inner task start/completion at 8.5/9.5h and later waves",
            "native zero-time preparation bookkeeping markers; NPSTA=0",
            "MSUF as completed-by-RCEND count (invalid interpretation)",
            "SIMPE #204 conversion rejection as dynamic cancellation (invalid interpretation)",
        ],
    }
    _write(output / "source-fingerprints.json", source)
    _write(output / "handoff-verification.json", handoff["verification"])
    accepted = True
    for case_id in ("A01", "A02"):
        # This producer has no parameter for a native expected result/schedule.
        artifacts = compile_case(case_id)
        aircraft_map = {
            artifacts.source_mapping["aircraft"]["canonical_tail_number"]:
                artifacts.source_mapping["aircraft"]["native_instance"]
        }
        mission_map = {item["engine_mission_id"]: item["native_mission_instance"]
                       for item in artifacts.source_mapping["missions"]}
        observed = extract_engine_observations(
            artifacts.plan, artifacts.result, case_id=case_id,
            aircraft_identity=aircraft_map, mission_identity=mission_map,
        )
        comparison = compare_observations(
            observed, handoff["expected"]["cases"][case_id], handoff["manifest"]["tolerances"],
            expected_source_inputs_sha256=json_digest(artifacts.canonical),
            expected_plan_fingerprint=artifacts.plan.fingerprint,
        )
        if case_id == "A01":
            controls = run_controls(artifacts, observed, handoff, aircraft_map, mission_map)
            _write(output / "negative-controls.json", controls)
            report["negative_controls_status"] = controls["status"]
            accepted = accepted and controls["status"] == "passed"
        case_path = output / case_id
        objects = {
            "canonical-input.json": artifacts.canonical,
            "business-ir.json": artifacts.business.to_dict(),
            "core-ir.json": artifacts.core.to_dict(),
            "execution-plan.json": artifacts.plan.to_dict(),
            "lineage.json": artifacts.lineage,
            "engine-result.json": artifacts.result,
            "source-mapping.json": artifacts.source_mapping,
            "observations.json": observed,
            "comparison.json": comparison,
        }
        for name, value in objects.items():
            _write(case_path / name, value)
        fingerprints = {name: sha256((case_path / name).read_bytes()) for name in objects}
        _write(case_path / "artifact-fingerprints.json", fingerprints)
        accepted = accepted and comparison["status"] == "matched"
        report["engine_identity_required"]["input_fingerprint"][case_id] = json_digest(artifacts.canonical)
        report["engine_identity_required"]["execution_plan_fingerprint"][case_id] = artifacts.plan.fingerprint
        report["mapping_required"]["aircraft_business_to_engine_id"][case_id] = aircraft_map
        report["mapping_required"]["mission_instance_to_engine_id"][case_id] = mission_map
        report["cases"][case_id] = {
            "status": comparison["status"],
            "observed_events": observed["mapped_events"],
            "observed_72_intervals": observed["intervals"],
            "integrals": observed["integrals"],
            "terminal_counts": observed["terminal"],
            "first_discrepancy": comparison["first_divergence"],
            "comparison_checks": comparison["check_count"],
            "failed_checks": comparison["failed_count"],
            "artifact_sha256": fingerprints,
            "native_only": observed["unsupported_native_observables"],
        }
    report["equivalence_status"] = (
        "matched_mapped_observables_not_full_equivalence" if accepted else "mismatch"
    )
    report["acceptance_note"] = (
        "Only A01/A02 deterministic one-aircraft mapped mission/binding observables: "
        "72 half-hour intervals, integrals, terminal counts, stable identities and event times. "
        "Notification is a commission-time proxy, not an independent captured notification; "
        "no same-time priority claim. No native re-execution, GUI acceptance, fault/resource/stock/"
        "cancellation/F35/J35 equivalence, RNG-stream equivalence or performance claim. "
        "SIMPE=36h is separate from RCEND; MSUF is not a window-end completion count."
    )
    _write(output / "consumer-report.json", report)
    index = {str(path.relative_to(output)): sha256(path.read_bytes())
             for path in sorted(output.rglob("*.json"))}
    _write(output / "evidence-index.json", {
        "schema": "a01-a02-engine-evidence-index/v1", "files": index,
        "index_excludes_itself": True,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args()
    report = execute_pairing(args.output, args.handoff)
    print(json.dumps({"engine_status": report["engine_status"],
                      "equivalence_status": report["equivalence_status"],
                      "cases": {key: {"status": value["status"],
                                      "check_count": value["comparison_checks"],
                                      "first_discrepancy": value["first_discrepancy"]}
                                for key, value in report["cases"].items()}}, indent=2))
    return 0 if report["equivalence_status"] == "matched_mapped_observables_not_full_equivalence" else 2


if __name__ == "__main__":
    raise SystemExit(main())
