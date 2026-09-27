"""Independent counterexamples: equal totals are not schedule conformance."""

from __future__ import annotations

import copy

from experiments.simlox_pairing.observations import (
    ObservationError,
    compare_observations,
    extract_engine_observations,
)
from sim_engine_compiler.compiler.layout import compile_core
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.reference import SimpyReferenceRuntime


def run_controls(artifacts, observed, handoff, aircraft_map, mission_map) -> dict:
    expected = handoff["expected"]["cases"]["A01"]
    tolerances = handoff["manifest"]["tolerances"]
    controls = []

    # Recompile and genuinely execute a changed schedule. No trace/result is
    # synthesized from native expectations, even for this negative control.
    changed = copy.deepcopy(artifacts.canonical)
    changed["mission_profile"]["composite_tasks"][0]["taskItems"][0]["firstWaveTime"] = "08:30"
    changed_plan = compile_core(lower_business(import_business_ir(changed)))
    changed_result = SimpyReferenceRuntime(changed_plan, seed=0).run()
    shifted = extract_engine_observations(
        changed_plan, changed_result, case_id="A01",
        aircraft_identity=aircraft_map, mission_identity=mission_map,
    )
    comparison = compare_observations(shifted, expected, tolerances)
    failed_bins = [check for check in comparison["checks"]
                   if check["status"] == "fail" and check["path"].startswith("intervals[")]
    controls.append({
        "control": "same_totals_wrong_schedule", "classification": "model_configuration",
        "detected": comparison["status"] == "mismatched" and bool(failed_bins),
        "same_integrals": shifted["integrals"] == observed["integrals"],
        "same_terminal_counts": shifted["terminal"] == observed["terminal"],
        "first_discrepancy": comparison["first_divergence"],
        "first_interval_discrepancy": failed_bins[0] if failed_bins else None,
        "changed_canonical": changed, "changed_plan": changed_plan.to_dict(),
        "actual_engine_result": changed_result,
    })

    wrong_identity = extract_engine_observations(
        artifacts.plan, artifacts.result, case_id="A01",
        aircraft_identity={key: "<WRONG-AIRCRAFT,0>" for key in aircraft_map},
        mission_identity=mission_map,
    )
    comparison = compare_observations(wrong_identity, expected, tolerances)
    controls.append({"control": "same_times_wrong_identity", "classification": "observation_mapping",
                     "detected": comparison["status"] == "mismatched",
                     "first_discrepancy": comparison["first_divergence"]})

    wrong_plan = copy.deepcopy(artifacts.result)
    wrong_plan["plan_fingerprint"] = "0" * 64
    try:
        extract_engine_observations(artifacts.plan, wrong_plan, case_id="A01",
                                    aircraft_identity=aircraft_map, mission_identity=mission_map)
    except ObservationError as error:
        controls.append({"control": "result_plan_mismatch", "classification": "evidence_binding",
                         "detected": error.code == "result_plan_mismatch",
                         "first_discrepancy": {"code": error.code, "path": error.path}})
    else:
        controls.append({"control": "result_plan_mismatch", "detected": False})

    comparison = compare_observations(observed, expected, tolerances,
                                      expected_source_inputs_sha256="0" * 64)
    controls.append({"control": "canonical_input_plan_mismatch", "classification": "evidence_binding",
                     "detected": comparison["status"] == "mismatched",
                     "first_discrepancy": comparison["first_divergence"]})
    passed = (all(item["detected"] for item in controls)
              and controls[0]["same_integrals"] and controls[0]["same_terminal_counts"])
    return {"schema": "a01-a02-pairing-negative-controls/v1",
            "status": "passed" if passed else "failed", "controls": controls}
