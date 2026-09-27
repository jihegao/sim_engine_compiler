from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from benchmarks.three_arm_v1.workloads import (
    DEFAULT_SIZES,
    STRUCTURAL_FAMILIES,
    build_structural_workload,
    ir_reuse_variants,
    persist_ir_reuse_artifacts,
    structural_workloads,
)
from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.compiler.layout import compile_core
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.ir.layers import BusinessIR, CoreIR
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
COMPILE_MLIR = ROOT / "scripts" / "compile_mlir_execution_plan.py"
RUNTIME = Path(
    os.environ.get(
        "SIM_ENGINE_RUNTIME_BIN",
        ROOT / "rust" / "runtime" / "target" / "release" / "sim-engine-runtime",
    )
)
REFERENCE_TOLERANCES = {
    "trace_business_projection": {"float_rel_tol": 0.0, "float_abs_tol": 0.0},
    "sample_requests": {"float_rel_tol": 0.0, "float_abs_tol": 0.0},
    # These synthetic cases are exact.  The formal J35 protocol separately
    # allows tolerance only for sample_requests[*].value_minutes.
    "metrics": {"float_rel_tol": 0.0, "float_abs_tol": 0.0},
    "terminal_state": {"float_rel_tol": 0.0, "float_abs_tol": 0.0},
}
WORKLOAD_COUNTER_FIELDS = (
    "resource_dispatch_phase_calls",
    "resource_dispatch_waiting_jobs_observed",
    "resource_dispatch_candidate_visits",
    "resource_dispatch_guard_evaluations",
    "resource_dispatch_cache_hits",
    "resource_dispatch_replay_visits",
    "resource_dispatch_index_lookups",
    "resource_dispatch_index_candidate_visits",
    "resource_dispatch_index_waiter_visits",
    "resource_dispatch_waiting_index_updates",
    "resource_dispatch_sort_items",
    "resource_dispatch_merge_inputs",
    "resource_dispatch_merge_insertions",
    "resource_dispatch_queue_updates",
    "resource_dispatch_queue_ns",
    "resource_dispatch_event_attempts",
)
REUSED_ACCEPTANCE_TESTS = (
    # Existing executable cases remain the semantic authority for behavior
    # orthogonal to the new waiting-set scale matrix.  The admission receipt
    # must execute these node IDs; merely importing them is not acceptance.
    "tests/differential/test_dependency_dispatch.py::DependencyDispatchTests::test_shared_suppliers_release_wakes_other_destination",
    "tests/differential/test_dependency_dispatch.py::DependencyDispatchTests::test_remote_capacity_arrival_release_and_cancel_wakeups",
    "tests/differential/test_dependency_dispatch.py::DependencyDispatchTests::test_existing_failure_preventive_transport_and_time_boundaries",
    "tests/conformance/test_b2_b3_reference.py::B3OrganizationInventoryTests::test_cancelled_waiting_job_returns_arrived_reservation",
)


def business_event_projection(result: dict) -> list[dict]:
    """Project stable business fields; omit representation-only trace fields."""

    return [
        {
            "time": event["time"],
            "phase": event["phase"],
            "kind": event["kind"],
            "entity": event["entity"],
            "rule_id": event.get("rule_id"),
            "source_path": event.get("source_path"),
            "details": event.get("details", {}),
        }
        for event in result["trace"]
    ]


def _assert_field_equal(
    case: unittest.TestCase, name: str, expected: object, actual: object
) -> None:
    tolerance = REFERENCE_TOLERANCES[name]
    divergence = first_divergence(expected, actual, path=name, **tolerance)
    case.assertIsNone(divergence, divergence)


class ThreeArmWorkloadDefinitionTests(unittest.TestCase):
    def test_invalid_or_ambiguous_scale_requests_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "unknown structural family"):
            build_structural_workload("unknown", 4)
        with self.assertRaisesRegex(ValueError, "integer >= 2"):
            build_structural_workload("low-contention", 1)
        with self.assertRaisesRegex(ValueError, "unique"):
            structural_workloads((4, 4))

    def test_structural_matrix_is_bounded_unique_and_explicitly_synthetic(self):
        workloads = structural_workloads()
        self.assertEqual(len(workloads), len(DEFAULT_SIZES) * len(STRUCTURAL_FAMILIES))
        self.assertEqual(len({item.case_id for item in workloads}), len(workloads))
        self.assertEqual(len({item.canonical_sha256 for item in workloads}), len(workloads))
        for item in workloads:
            with self.subTest(case=item.case_id):
                self.assertEqual(item.provenance["classification"], "synthetic-structural-workload")
                self.assertFalse(item.provenance["j35_claim"])
                self.assertIsNone(item.provenance["upstream_case"])
                self.assertEqual(len(item.canonical_inputs["aircraft"]["assets"]), item.size)
                self.assertEqual(
                    item.canonical_inputs["project_identity"]["project_id"], item.case_id
                )

    def test_structural_families_create_expected_waiting_pressure(self):
        capacities = {}
        delays = {}
        for workload in structural_workloads():
            family = workload.family
            plan = compile_aircraft_support(workload.fresh_inputs())
            result = SimpyReferenceRuntime(plan, seed=0).run()
            event_kinds = {event["kind"] for event in result["trace"]}
            key = (family, workload.size)
            capacities[key] = tuple(
                node.personnel_capacity for node in plan.resource_nodes
            )
            delays[key] = sum(
                event["kind"] == "personnel_delay" for event in result["trace"]
            )
            for expected in workload.expected_business_events:
                self.assertIn(expected, event_kinds)
        for size in DEFAULT_SIZES:
            self.assertEqual(capacities[("low-contention", size)], (size,))
            sparse = capacities[("sparse-affected", size)]
            self.assertGreater(len(sparse), 1)
            self.assertEqual(sum(sparse), size - len(sparse))
            self.assertLessEqual(max(sparse), 3)
            self.assertEqual(capacities[("dense-affected", size)], (1,))
            self.assertEqual(delays[("low-contention", size)], 0)
            self.assertGreater(delays[("sparse-affected", size)], 0)
            self.assertGreater(
                delays[("dense-affected", size)],
                delays[("sparse-affected", size)],
            )

    def test_business_ir_variants_round_trip_and_recompile_without_runtime_edits(self):
        variants = ir_reuse_variants(size=8)
        self.assertEqual(
            {variant.dimension for variant in variants},
            {"mission-frequency", "resource-counts", "process-composition"},
        )
        self.assertEqual(len({variant.origin_canonical_sha256 for variant in variants}), 1)

        plans = {}
        with tempfile.TemporaryDirectory(prefix="three-arm-ir-reuse-") as temporary:
            directory = Path(temporary)
            for variant in variants:
                with self.subTest(variant=variant.dimension):
                    business_path = directory / f"{variant.dimension}-business.json"
                    core_path = directory / f"{variant.dimension}-core.json"
                    plan_path = directory / f"{variant.dimension}-plan.json"
                    business_path.write_text(json.dumps(variant.business_ir))
                    restored_business = BusinessIR.from_dict(
                        json.loads(business_path.read_text())
                    )
                    core = lower_business(restored_business)
                    core_path.write_text(json.dumps(core.to_dict()))
                    restored_core = CoreIR.from_dict(json.loads(core_path.read_text()))
                    plan = compile_core(restored_core)
                    plan_path.write_text(json.dumps(plan.to_dict()))
                    restored_plan = ExecutionPlan.from_dict(
                        json.loads(plan_path.read_text())
                    )
                    self.assertEqual(restored_plan, plan)
                    self.assertEqual(
                        core.payload["source"]["origin_canonical_sha256"],
                        variant.origin_canonical_sha256,
                    )
                    plans[variant.dimension] = plan

        self.assertEqual(len(plans["mission-frequency"].missions), 4)
        self.assertEqual(plans["resource-counts"].resource_nodes[0].personnel_capacity, 4)
        self.assertEqual(len(plans["process-composition"].activities[0].steps), 2)
        self.assertEqual(
            plans["process-composition"].activities[0].steps[1].predecessors, (0,)
        )
        self.assertEqual(len({plan.fingerprint for plan in plans.values()}), 3)

    def test_ir_reuse_evidence_manifest_binds_reloadable_artifacts(self):
        with tempfile.TemporaryDirectory(prefix="three-arm-reuse-evidence-") as temporary:
            output = Path(temporary)
            manifest = persist_ir_reuse_artifacts(output)
            self.assertEqual(manifest["schema_version"], "three-arm-ir-reuse-artifacts/v1")
            self.assertFalse(manifest["j35_claim"])
            self.assertEqual(len(manifest["variants"]), 6)
            for variant in manifest["variants"]:
                for record in variant["artifacts"].values():
                    path = output / record["path"]
                    self.assertEqual(
                        hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"]
                    )
                business_record = variant["artifacts"]["business"]
                BusinessIR.from_dict(
                    json.loads((output / business_record["path"]).read_text())
                )
                if variant["semantic_profile"] == "legacy-minute-v1":
                    self.assertEqual(variant["reference_status"], "generated")
                    self.assertIn("reference_result", variant["artifacts"])
                else:
                    self.assertEqual(
                        variant["reference_status"],
                        "unsupported-event-time-python-reference",
                    )


class ThreeArmRustDifferentialTests(unittest.TestCase):
    """Exact same-kernel acceptance; no timing or build occurs in this suite."""

    @classmethod
    def setUpClass(cls):
        cls.plugin = Path(
            os.environ.get(
                "SIM_ENGINE_MLIR_PLUGIN_DIR", ROOT / "tools" / "mlir_dispatch" / "build-make"
            )
        )
        explicit_mlir = os.environ.get("SIM_ENGINE_MLIR_OPT")
        prefix = os.environ.get("MLIR_PREFIX")
        cls.mlir = Path(explicit_mlir) if explicit_mlir else (
            Path(prefix) / "bin" / "mlir-opt" if prefix else Path("/missing/mlir-opt")
        )
        missing = [
            path
            for path in (
                RUNTIME,
                cls.mlir,
                cls.plugin / "SimDialect.so",
                cls.plugin / "SimResourceDispatchPass.so",
            )
            if not path.is_file()
        ]
        if missing:
            message = "three-arm semantic acceptance requires prebuilt runtime and pinned MLIR 23.1.1: " + ", ".join(map(str, missing))
            if os.environ.get("SIM_ENGINE_REQUIRE_THREE_ARM") == "1":
                raise AssertionError(message)
            raise unittest.SkipTest(message)

    def compile_indexed(self, source: dict, directory: Path, name: str) -> tuple[Path, Path]:
        source_path = directory / f"{name}-source.json"
        indexed = directory / f"{name}-indexed.json"
        scan = directory / f"{name}-scan.json"
        source_path.write_text(json.dumps(source))
        completed = subprocess.run(
            [
                sys.executable,
                str(COMPILE_MLIR),
                str(source_path),
                str(indexed),
                "--plugin-dir",
                str(self.plugin),
                "--mlir-opt",
                str(self.mlir),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        raw = json.loads(indexed.read_text())
        self.assertEqual(
            raw["resource_dispatch_index"]["schema_version"],
            "resource-dispatch-index/v2",
        )
        raw.pop("resource_dispatch_index")
        scan.write_text(json.dumps(raw))
        return scan, indexed

    def run_one(
        self,
        plan: Path,
        directory: Path,
        name: str,
        *,
        seed: int,
        observation: str,
        candidates: bool,
        until: int | None = None,
    ) -> tuple[dict, dict]:
        output = directory / f"{name}-result.json"
        profile = directory / f"{name}-profile.json"
        command = [
            str(RUNTIME),
            str(plan),
            str(output),
            "--seed",
            str(seed),
            "--observation-level",
            observation,
            "--profile-output",
            str(profile),
        ]
        if candidates:
            command.append("--dependency-dispatch")
        if until is not None:
            command.extend(("--until", str(until)))
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        counters = json.loads(profile.read_text())["profile"]
        for field in WORKLOAD_COUNTER_FIELDS:
            self.assertIn(field, counters)
        return json.loads(output.read_text()), counters

    def assert_reference_fields(self, reference: dict, actual: dict) -> None:
        _assert_field_equal(
            self,
            "trace_business_projection",
            business_event_projection(reference),
            business_event_projection(actual),
        )
        for field in ("sample_requests", "metrics", "terminal_state"):
            _assert_field_equal(self, field, reference[field], actual[field])
        self.assertEqual(
            (actual["time"], actual["stop_reason"]),
            (reference["time"], reference["stop_reason"]),
        )

    def assert_three_arms(
        self,
        scan: Path,
        indexed: Path,
        directory: Path,
        name: str,
        *,
        seed: int = 0,
        observation: str = "full",
        reference: dict | None = None,
    ) -> dict:
        baseline, scan_profile = self.run_one(
            scan, directory, f"{name}-scan", seed=seed,
            observation=observation, candidates=False,
        )
        cached, _cache_profile = self.run_one(
            indexed, directory, f"{name}-cache", seed=seed,
            observation=observation, candidates=False,
        )
        candidate, candidate_profile = self.run_one(
            indexed, directory, f"{name}-candidates", seed=seed,
            observation=observation, candidates=True,
        )
        self.assertEqual(baseline, cached)
        self.assertEqual(baseline, candidate)
        if reference is not None:
            self.assert_reference_fields(reference, baseline)
        self.assertLessEqual(
            candidate_profile["resource_dispatch_guard_evaluations"],
            scan_profile["resource_dispatch_guard_evaluations"],
        )
        return baseline

    def test_representative_structural_cases_match_reference_and_both_time_profiles(self):
        with tempfile.TemporaryDirectory(prefix="three-arm-structural-") as temporary:
            directory = Path(temporary)
            for family in STRUCTURAL_FAMILIES:
                workload = build_structural_workload(family, 4)
                legacy_inputs = workload.fresh_inputs()
                reference_plan = compile_aircraft_support(
                    legacy_inputs, semantic_profile="legacy-minute-v1"
                )
                reference = SimpyReferenceRuntime(reference_plan, seed=0).run()
                for observation in ("full", "summary"):
                    expected = reference if observation == "full" else {
                        **reference,
                        "trace": [],
                    }
                    results = {}
                    for semantic_profile in ("legacy-minute-v1", "event-time-v2"):
                        business = import_business_ir_for_test(legacy_inputs, semantic_profile)
                        scan, indexed = self.compile_indexed(
                            business.to_dict(), directory,
                            f"{family}-{semantic_profile}-{observation}",
                        )
                        results[semantic_profile] = self.assert_three_arms(
                            scan,
                            indexed,
                            directory,
                            f"{family}-{semantic_profile}-{observation}",
                            observation=observation,
                            reference=expected,
                        )
                    # The profile is part of the Plan identity; compare the stable
                    # business/RNG fields rather than the plan_fingerprint field.
                    self.assert_reference_fields(
                        results["legacy-minute-v1"], results["event-time-v2"]
                    )

    def test_persisted_business_ir_variants_match_three_arms_and_reference(self):
        with tempfile.TemporaryDirectory(prefix="three-arm-variants-") as temporary:
            directory = Path(temporary)
            for variant in ir_reuse_variants(size=8, semantic_profile="legacy-minute-v1"):
                business = variant.restore()
                reference_plan = compile_core(lower_business(business))
                reference = SimpyReferenceRuntime(reference_plan, seed=7).run()
                scan, indexed = self.compile_indexed(
                    variant.business_ir, directory, variant.dimension
                )
                self.assert_three_arms(
                    scan,
                    indexed,
                    directory,
                    variant.dimension,
                    seed=7,
                    reference=reference,
                )

    def test_repeated_seed_batch_is_thread_invariant_for_all_three_arms(self):
        workload = build_structural_workload("dense-affected", 4)
        business = import_business_ir_for_test(
            workload.fresh_inputs(), "event-time-v2"
        )
        seeds = "7,0,7,1"
        with tempfile.TemporaryDirectory(prefix="three-arm-threads-") as temporary:
            directory = Path(temporary)
            scan, indexed = self.compile_indexed(
                business.to_dict(), directory, "thread-invariance"
            )
            arms = (("scan", scan, False), ("cache", indexed, False), ("candidates", indexed, True))
            common_samples = None
            for arm, plan, candidates in arms:
                per_thread = []
                for threads in (1, 3):
                    output = directory / f"{arm}-{threads}.json"
                    command = [
                        str(RUNTIME), str(plan), str(output),
                        "--seeds", seeds,
                        "--worker-threads", str(threads),
                        "--observation-level", "summary",
                    ]
                    if candidates:
                        command.append("--dependency-dispatch")
                    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    value = json.loads(output.read_text())
                    self.assertEqual(
                        [sample["sample_index"] for sample in value["samples"]],
                        [0, 1, 2, 3],
                    )
                    per_thread.append(value["samples"])
                self.assertEqual(per_thread[0], per_thread[1])
                if common_samples is None:
                    common_samples = per_thread[0]
                else:
                    self.assertEqual(common_samples, per_thread[0])

    def test_n64_sparse_changes_visit_smaller_fraction_of_exposed_waiters(self):
        profiles = {}
        with tempfile.TemporaryDirectory(prefix="three-arm-sparsity-") as temporary:
            directory = Path(temporary)
            for family in ("sparse-affected", "dense-affected"):
                workload = build_structural_workload(family, 64)
                business = import_business_ir_for_test(
                    workload.fresh_inputs(), "event-time-v2"
                )
                _, indexed = self.compile_indexed(
                    business.to_dict(), directory, family
                )
                _, profiles[family] = self.run_one(
                    indexed,
                    directory,
                    family,
                    seed=0,
                    observation="summary",
                    candidates=True,
                )

        def affected_fraction(profile: dict) -> float:
            self.assertGreater(profile["resource_dispatch_waiting_jobs_observed"], 0)
            return (
                profile["resource_dispatch_index_waiter_visits"]
                / profile["resource_dispatch_waiting_jobs_observed"]
            )

        self.assertLess(
            affected_fraction(profiles["sparse-affected"]),
            affected_fraction(profiles["dense-affected"]),
        )


def import_business_ir_for_test(inputs: dict, semantic_profile: str) -> BusinessIR:
    # Local import keeps the test's dependency on the sole canonical Adapter
    # visible and avoids a second Project JSON interpretation path.
    from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir

    return import_business_ir(inputs, semantic_profile=semantic_profile)


if __name__ == "__main__":
    unittest.main()
