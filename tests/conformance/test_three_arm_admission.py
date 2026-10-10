import copy
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.three_arm_v1 import admission
from benchmarks.three_arm_v1.admission import compare


def result_fixture():
    return {
        "plan_fingerprint": "plan-a",
        "seed": 7,
        "time": 60,
        "stop_reason": "duration",
        "sample_requests": [
            {
                "stream": "component/f35-01/radar/0",
                "reason": "initialize",
                "value_minutes": 1.0,
            },
            {
                "stream": "component/f35-02/radar/0",
                "reason": "repair_complete",
                "value_minutes": 1000.0,
            },
        ],
        "trace": [
            {"time": 1, "kind": "job_started", "entity": "job-1", "score": 0.25},
            {"time": 2, "kind": "job_completed", "entity": "job-1", "score": 0.5},
        ],
        "metrics": {"ready_rate": 0.75, "completed_sorties": 1},
        "terminal_state": {
            "aircraft": [{"tail_number": "F35-01", "flight_hours": 1.5}],
            "jobs": [{"job_id": "job-1", "state": "completed"}],
        },
    }


class ThreeArmAdmissionCompareTests(unittest.TestCase):
    def test_reference_boundary_allows_only_value_minutes_roundoff(self):
        left = result_fixture()
        right = copy.deepcopy(left)
        right["sample_requests"][0]["value_minutes"] += 5e-13
        right["sample_requests"][1]["value_minutes"] += 1e-12

        compare(left, right, reference=True)

        with self.assertRaisesRegex(
            AssertionError, r"root\.sample_requests\[0\]\.value_minutes"
        ):
            compare(left, right, reference=False)

    def test_reference_boundary_rejects_value_minutes_outside_tolerance(self):
        left = result_fixture()
        right = copy.deepcopy(left)
        right["sample_requests"][0]["value_minutes"] += 2e-12

        with self.assertRaisesRegex(
            AssertionError, r"root\.sample_requests\[0\]\.value_minutes"
        ):
            compare(left, right, reference=True)

    def test_reference_boundary_rejects_every_other_result_discrepancy(self):
        mutations = {
            "timestamp": (
                lambda value: value["trace"][0].__setitem__("time", 2),
                r"root\.trace\[0\]\.time",
            ),
            "rng stream": (
                lambda value: value["sample_requests"][0].__setitem__("stream", "other"),
                r"root\.sample_requests\[0\]\.stream",
            ),
            "rng reason": (
                lambda value: value["sample_requests"][0].__setitem__("reason", "other"),
                r"root\.sample_requests\[0\]\.reason",
            ),
            "metric": (
                lambda value: value["metrics"].__setitem__("ready_rate", 0.7500000000005),
                r"root\.metrics\.ready_rate",
            ),
            "terminal state": (
                lambda value: value["terminal_state"]["aircraft"][0].__setitem__(
                    "flight_hours", 1.5000000000005
                ),
                r"root\.terminal_state\.aircraft\[0\]\.flight_hours",
            ),
            "trace float": (
                lambda value: value["trace"][0].__setitem__("score", 0.2500000000005),
                r"root\.trace\[0\]\.score",
            ),
            "trace identity": (
                lambda value: value["trace"][0].__setitem__("entity", "job-2"),
                r"root\.trace\[0\]\.entity",
            ),
        }
        left = result_fixture()
        for label, (mutate, expected_path) in mutations.items():
            with self.subTest(label=label):
                right = copy.deepcopy(left)
                mutate(right)
                with self.assertRaisesRegex(AssertionError, expected_path):
                    compare(left, right, reference=True)

    def test_nonfinite_values_are_rejected_even_at_permitted_path(self):
        for nonfinite in (math.nan, math.inf, -math.inf):
            with self.subTest(nonfinite=nonfinite):
                left = result_fixture()
                right = copy.deepcopy(left)
                left["sample_requests"][0]["value_minutes"] = nonfinite
                right["sample_requests"][0]["value_minutes"] = nonfinite
                with self.assertRaisesRegex(
                    AssertionError,
                    r"root\.sample_requests\[0\]\.value_minutes: nonfinite value",
                ):
                    compare(left, right, reference=True)

    def test_exact_types_are_required(self):
        mutations = {
            "integer to float": lambda value: value.__setitem__("time", 60.0),
            "integer to boolean": lambda value: value["metrics"].__setitem__(
                "completed_sorties", True
            ),
            "list to tuple": lambda value: value.__setitem__(
                "sample_requests", tuple(value["sample_requests"])
            ),
        }
        left = result_fixture()
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                right = copy.deepcopy(left)
                mutate(right)
                with self.assertRaisesRegex(AssertionError, r": type \w+ != \w+"):
                    compare(left, right, reference=True)

    def test_list_order_and_membership_are_exact(self):
        left = result_fixture()
        mutations = {
            "sample request order": lambda value: value["sample_requests"].reverse(),
            "trace order": lambda value: value["trace"].reverse(),
            "trace length": lambda value: value["trace"].pop(),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                right = copy.deepcopy(left)
                mutate(right)
                with self.assertRaises(AssertionError):
                    compare(left, right, reference=True)

    def test_mapping_keys_are_exact(self):
        left = result_fixture()
        right = copy.deepcopy(left)
        right["metrics"]["extra"] = 1

        with self.assertRaisesRegex(AssertionError, r"root\.metrics: keys differ"):
            compare(left, right, reference=True)


def profile_fixture(arm="scan"):
    profile = {
        field: 0
        for field in admission.PROFILE_COUNTER_FIELDS | admission.PROFILE_TIMING_FIELDS
    }
    profile.update(
        execution_ns=10,
        resource_dispatch_phase_calls=2,
        resource_dispatch_waiting_jobs_observed=4,
        resource_dispatch_sort_items=4 if arm in ("scan", "cache") else 0,
        resource_dispatch_merge_inputs=3 if arm == "candidates" else 0,
        resource_dispatch_merge_insertions=2 if arm == "candidates" else 0,
        resource_dispatch_candidate_visits=4,
        resource_dispatch_guard_evaluations=3,
        resource_dispatch_cache_hits=1,
        resource_dispatch_event_attempts=2,
        trace_events_attempted=3,
        trace_events_materialized=2,
        phases={"resource_dispatch": {"calls": 2, "elapsed_ns": 5}},
    )
    return {
        "plan_load_ns": 1,
        "initialization_ns": 2,
        "execution_ns": 10,
        "result_write_ns": 3,
        "process_wall_ns": 20,
        "profile": profile,
    }


class ThreeArmAdmissionGateControlTests(unittest.TestCase):
    def test_verification_contract_freezes_commands_and_mlir_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            python = root / "venv/bin/python"
            plugin = root / "plugins"
            plugin.mkdir()
            for name in ("SimDialect.so", "SimResourceDispatchPass.so"):
                (plugin / name).write_bytes(name.encode())
            mlir = root / "llvm/bin/mlir-opt"
            mlir.parent.mkdir(parents=True)
            mlir.write_bytes(b"mlir-opt-23.1.1")

            commands = admission.expected_verification_commands(python, plugin, mlir)
            self.assertEqual(set(commands), admission.REQUIRED_CHECK_IDS)
            self.assertNotIn("-k", [item for command in commands.values() for item in command])
            self.assertEqual(
                commands["driver-controls"][-4:],
                [
                    "tests.conformance.test_three_arm_driver",
                    "tests.conformance.test_three_arm_summary",
                    "tests.conformance.test_cpu_batch_baseline",
                    "-v",
                ],
            )
            environment = admission.expected_verification_environment(plugin, mlir)
            self.assertEqual(
                environment["variables"]["LD_LIBRARY_PATH"], str(root / "llvm/lib")
            )
            self.assertEqual(
                environment["artifacts"]["mlir_opt"]["sha256"], admission.sha(mlir)
            )
            self.assertEqual(set(environment["artifacts"]["plugins"]), {
                "SimDialect.so", "SimResourceDispatchPass.so"
            })

    def test_profile_requires_all_workload_fields_and_logical_invariants(self):
        for arm in ("scan", "cache", "candidates"):
            with self.subTest(arm=arm):
                admission.validate_profile_output(profile_fixture(arm), arm=arm)

        mutations = {
            "missing event counter": lambda value: value["profile"].pop(
                "resource_dispatch_event_attempts"
            ),
            "negative queue time": lambda value: value["profile"].__setitem__(
                "resource_dispatch_queue_ns", -1
            ),
            "merge inserts exceed inputs": lambda value: value["profile"].update(
                resource_dispatch_merge_inputs=1,
                resource_dispatch_merge_insertions=2,
            ),
            "dispatch events exceed trace": lambda value: value["profile"].update(
                resource_dispatch_event_attempts=4,
                trace_events_attempted=3,
            ),
            "scan workload missing sort": lambda value: value["profile"].__setitem__(
                "resource_dispatch_sort_items", 3
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                value = profile_fixture("scan")
                mutate(value)
                with self.assertRaises(ValueError):
                    admission.validate_profile_output(value, arm="scan")

    def test_subset_or_reordered_cases_are_partial_and_nonadmissible(self):
        frozen = ["j35", "small", "large"]
        self.assertEqual(admission.admission_status(frozen, frozen), ("passed", True))
        self.assertEqual(
            admission.admission_status(frozen[:2], frozen), ("partial", False)
        )
        self.assertEqual(
            admission.admission_status(list(reversed(frozen)), frozen),
            ("partial", False),
        )

    def test_profile_manifest_requires_all_sixty_unique_combinations(self):
        cases = [f"case-{index}" for index in range(10)]
        records = [
            {
                "case": case,
                "input_sha256": f"{index:064x}",
                "arm": arm,
                "level": level,
                "seed": 0,
                "profile_path": f"/evidence/{case}-{arm}-{level}.json",
                "workload_fields_validated": True,
                "timing_fields_semantic": False,
                "passed": True,
            }
            for index, case in enumerate(cases, start=1)
            for arm in ("scan", "cache", "candidates")
            for level in ("full", "summary")
        ]
        keys = admission.validate_profile_manifest(
            records, cases, require_complete=True
        )
        self.assertEqual(len(keys), 60)
        for mutation in (
            lambda value: value.pop(),
            lambda value: value.append(copy.deepcopy(value[0])),
            lambda value: value[0].__setitem__("timing_fields_semantic", True),
            lambda value: value[0].__setitem__("seed", 1),
        ):
            candidate = copy.deepcopy(records)
            mutation(candidate)
            with self.assertRaises(ValueError):
                admission.validate_profile_manifest(
                    candidate, cases, require_complete=True
                )

    def test_dirty_tracked_or_untracked_source_is_rejected(self):
        admission.require_clean_source_state("")
        for status in (" M rust/runtime/src/runtime.rs", "?? fabricated-receipt.json"):
            with self.subTest(status=status), self.assertRaisesRegex(
                ValueError, "committed clean tracked/untracked source"
            ):
                admission.require_clean_source_state(status)

    def test_receipt_rejects_fabricated_success_and_unbound_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            logs = {}
            for check_id in admission.REQUIRED_CHECK_IDS:
                path = root / f"{check_id}.log"
                path.write_text(
                    "running 1 test\n"
                    "test result: ok. 1 passed; 0 failed; 0 ignored; "
                    "0 measured; 0 filtered out\n"
                    if check_id == "rust-unit"
                    else "Ran 1 test in 0.001s\n\nOK\n"
                )
                logs[check_id] = path
            reuse = root / "runs/three-arm-v1/reuse/manifest.json"
            reuse.parent.mkdir(parents=True)
            reuse.write_text(
                json.dumps(
                    {
                        "schema_version": "three-arm-ir-reuse-artifacts/v1",
                        "variants": [{"case_id": "reuse-1"}],
                    }
                )
            )
            build_log = root / "build.log"
            build_log.write_text("Finished `release` profile [optimized] target(s)\n")
            binaries = {}
            expected_binaries = {}
            for name in ("sim-engine-runtime", "stage-c-benchmark"):
                path = root / name
                path.write_bytes(name.encode())
                expected_binaries[name] = path
                binaries[name] = {"path": str(path), "sha256": admission.sha(path)}
            raw_paths = [*logs.values(), reuse, build_log]
            raw_files = {str(path): admission.sha(path) for path in raw_paths}
            commands = admission.expected_verification_commands(
                root / "venv/python", root / "plugin", root / "bin/mlir-opt"
            )
            environment = {"pinned": "test-environment"}
            receipt = {
                "schema_version": admission.RECEIPT_SCHEMA,
                "status": "passed",
                "source_commit": "abc123",
                "environment": environment,
                "checks": [
                    {
                        "id": check_id,
                        "command": commands[check_id],
                        "passed": True,
                        "exit_code": 0,
                        "log_path": str(logs[check_id]),
                    }
                    for check_id in sorted(admission.REQUIRED_CHECK_IDS)
                ],
                "raw_files": raw_files,
                "build": {
                    "command": admission.BUILD_COMMAND,
                    "passed": True,
                    "exit_code": 0,
                    "source_commit": "abc123",
                    "rustc_vv": "rustc 1.90.0 (fake)",
                    "source_files": {"rust/runtime/src/lib.rs": "source-sha"},
                    "log_path": str(build_log),
                    "binaries": binaries,
                },
            }
            with patch.object(
                admission,
                "build_source_files",
                return_value={"rust/runtime/src/lib.rs": "source-sha"},
            ):
                admission.validate_regression_receipt(
                    receipt,
                    source_commit="abc123",
                    expected_binaries=expected_binaries,
                    rustc_vv="rustc 1.90.0 (fake)",
                    expected_commands=commands,
                    expected_environment=environment,
                )
                def fabricate_success_log(value):
                    path = logs["dispatch-regression"]
                    path.write_text("claimed passed\n")
                    value["raw_files"][str(path)] = admission.sha(path)

                def zero_test_log(value):
                    path = logs["admission-controls"]
                    path.write_text("Ran 0 tests in 0.000s\n\nOK\n")
                    value["raw_files"][str(path)] = admission.sha(path)

                def skipped_test_log(value):
                    path = logs["driver-controls"]
                    path.write_text("Ran 1 test in 0.001s\n\nOK (skipped=1)\n")
                    value["raw_files"][str(path)] = admission.sha(path)

                corruptions = {
                    "claimed check failure": lambda value: value["checks"][0].__setitem__(
                        "exit_code", 1
                    ),
                    "missing required check": lambda value: value["checks"].pop(),
                    "fabricated log success": fabricate_success_log,
                    "zero-test success": zero_test_log,
                    "skipped-test success": skipped_test_log,
                    "filtered command": lambda value: value["checks"][0]["command"].extend(
                        ["-k", "nonexistent"]
                    ),
                    "unbound build log": lambda value: value["raw_files"].pop(
                        str(build_log)
                    ),
                    "binary hash mismatch": lambda value: value["build"]["binaries"][
                        "sim-engine-runtime"
                    ].__setitem__("sha256", "0" * 64),
                }
                for label, corrupt in corruptions.items():
                    with self.subTest(label=label):
                        candidate = copy.deepcopy(receipt)
                        original_logs = {
                            check_id: path.read_text() for check_id, path in logs.items()
                        }
                        corrupt(candidate)
                        try:
                            with self.assertRaises(ValueError):
                                admission.validate_regression_receipt(
                                    candidate,
                                    source_commit="abc123",
                                    expected_binaries=expected_binaries,
                                    rustc_vv="rustc 1.90.0 (fake)",
                                    expected_commands=commands,
                                    expected_environment=environment,
                                )
                        finally:
                            for check_id, text in original_logs.items():
                                logs[check_id].write_text(text)


if __name__ == "__main__":
    unittest.main()
