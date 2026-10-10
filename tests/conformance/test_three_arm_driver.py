from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = ROOT / "benchmarks" / "three_arm_v1" / "driver.py"
SPEC = importlib.util.spec_from_file_location("three_arm_driver", DRIVER_PATH)
assert SPEC is not None and SPEC.loader is not None
driver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(driver)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _plan(source_inputs_sha256: str = "0" * 64) -> dict[str, object]:
    return {
        "plan_version": "execution-plan/v3",
        "source_inputs_sha256": source_inputs_sha256,
        "semantic_profile": "event-time-v2",
        "work_policy": "stable-topological-serial",
        "rng_profile": "legacy-sequential-v1",
    }


def _reference_comparisons() -> dict[str, object]:
    return {
        "trace_business_projection": {"passed": True, "exact": True},
        "sample_requests": {
            "passed": True,
            "exact": False,
            "float_fields": ["sample_requests[*].value_minutes"],
            "rel_tol": 2e-15,
            "abs_tol": 1e-12,
        },
        "metrics": {"passed": True, "exact": True},
        "terminal_state": {"passed": True, "exact": True},
    }


class ThreeArmDriverTests(unittest.TestCase):
    def _fixture(self, directory: str) -> tuple[argparse.Namespace, Path]:
        root = Path(directory).resolve()
        binary = root / "stage-c-benchmark"
        runtime = root / "sim-engine-runtime"
        gnu_time = root / "time"
        taskset = root / "taskset"
        for executable in (binary, runtime, gnu_time, taskset):
            executable.write_bytes(b"synthetic executable")
            executable.chmod(0o755)
        evidence: list[Path] = []
        for name, value in (
            ("PROTOCOL.md", "frozen protocol"),
            (
                "upstream-manifest.json",
                {
                    "spare_mvp_commit": driver.J35_UPSTREAM_COMMIT,
                    "canonical_file_sha256": "ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793",
                    "adapter": "src.spare_mvp_contract.adapter.SimulationAdapter.compile_scenario",
                },
            ),
            (
                "artifacts.json",
                {
                    "source_commit": "frozen-head",
                    "source_tree": "1" * 40,
                    "files": {str(binary): driver.sha256_file(binary)},
                    "rustc": "rustc 1.90.0 (synthetic)",
                    "cargo": "cargo 1.90.0 (synthetic)",
                },
            ),
            (
                "regression-receipt.json",
                {
                    "status": "passed",
                    "checks": [{"check": "regression", "passed": True}],
                    "raw_files": {"synthetic.log": "f" * 64},
                },
            ),
        ):
            path = root / name
            if isinstance(value, str):
                path.write_text(value, encoding="utf-8")
            else:
                _write_json(path, value)
            evidence.append(path)
        source_audit = root / "source-audit.json"
        _write_json(
            source_audit,
            {
                "schema_version": "three-arm-source-audit/v1",
                "upstream": {"head": driver.J35_UPSTREAM_COMMIT},
                "canonical_identity": {
                    "canonical_semantic_digest": driver.J35_CANONICAL_SEMANTIC_SHA256
                },
                "result": {
                    "j35_source_provenance_verified": True,
                    "canonical_export_byte_reproducible": True,
                },
            },
        )
        evidence.append(source_audit)
        cases = []
        gate_cases = {}
        checks = []
        plans_by_input: dict[str, tuple[Path, Path, Path, str]] = {}
        for index, case_id in enumerate(driver.EXPECTED_CASE_IDS):
            observation = "full" if index == 10 else "summary"
            input_key = "j35" if case_id == "j35-full" else case_id
            if input_key not in plans_by_input:
                if input_key == "j35":
                    input_path = (
                        ROOT
                        / "benchmarks/batch_preparation/results/amd128-j35-20260926/source/simulation-inputs.json"
                    )
                    input_value = json.loads(input_path.read_text(encoding="utf-8"))
                    input_sha256 = driver.J35_CANONICAL_SEMANTIC_SHA256
                else:
                    input_path = root / input_key / "canonical.json"
                    input_value = {"case_id": input_key, "ordinal": min(index, 9)}
                    input_sha256 = driver.sha256_bytes(driver._canonical_json(input_value))
                    _write_json(input_path, input_value)
                scan = root / input_key / "scan.json"
                indexed = root / input_key / "indexed.json"
                _write_json(scan, _plan(input_sha256))
                _write_json(
                    indexed,
                    {
                        **_plan(input_sha256),
                        "resource_dispatch_index": {
                            "schema_version": "resource-dispatch-index/v2"
                        },
                    },
                )
                plans_by_input[input_key] = (input_path, scan, indexed, input_sha256)
                evidence.extend((input_path, scan, indexed))
            input_path, scan, indexed, input_sha256 = plans_by_input[input_key]
            cases.append(
                {
                    "id": case_id,
                    "scan_plan": str(scan),
                    "indexed_plan": str(indexed),
                    "semantic_profile": "event-time-v2",
                    "observation_level": observation,
                }
            )
            profile_outputs = []
            for arm in driver.ARMS:
                profile_path = root / input_key / f"{observation}-{arm}-profile.json"
                _write_json(profile_path, {"profile": arm, "level": observation})
                evidence.append(profile_path)
                profile_outputs.append(
                    {
                        "arm": arm,
                        "level": observation,
                        "seed": 0,
                        "profile_path": str(profile_path),
                        "workload_fields_validated": True,
                        "timing_fields_semantic": False,
                        "passed": True,
                    }
                )
            gate_cases[case_id] = {
                "input_path": str(input_path),
                "input_sha256": input_sha256,
                "semantic_profile": "event-time-v2",
                "observation_level": observation,
                "seeds": [0, 1, 7],
                "untils": [None],
                "plans": {
                    "scan_sha256": driver.sha256_file(scan),
                    "indexed_sha256": driver.sha256_file(indexed),
                    "plan_fingerprint": "f" * 64,
                },
                "comparisons": {
                    "rust_three_arm_exact": True,
                    "reference": _reference_comparisons(),
                    "threads": {
                        "counts": [1, 3],
                        "duplicate_seed_order_exact": True,
                    },
                },
                "profile_validation": {
                    "workload_counters_validated": True,
                    "timing_fields_used_as_semantic_evidence": False,
                    "outputs": profile_outputs,
                },
                "result_sha256_by_seed": {
                    "0": "a" * 64,
                    "1": "b" * 64,
                    "7": "c" * 64,
                },
            }
            if case_id != "j35-full":
                checks.extend(
                    {"case": case_id, "check": "reference-legacy", "seed": seed, "passed": True}
                    for seed in driver.SEEDS
                )
                checks.extend(
                    {
                        "case": case_id,
                        "check": "three-arm/profile/observation",
                        "arm": arm,
                        "seed": seed,
                        "passed": True,
                    }
                    for arm in driver.ARMS
                    for seed in driver.SEEDS
                )
                checks.extend(
                    {
                        "case": case_id,
                        "check": "batch-order-duplicate-thread",
                        "arm": arm,
                        "level": level,
                        "threads": threads,
                        "passed": True,
                    }
                    for arm in driver.ARMS
                    for level in ("full", "summary")
                    for threads in (1, 3)
                )
        plan_map = root / "plan-map.json"
        gate = root / "gate.json"
        _write_json(plan_map, {"schema_version": driver.PLAN_MAP_SCHEMA, "cases": cases})
        evidence.extend((plan_map, binary))
        profile_manifest = []
        for case_id in driver.EXPECTED_CASE_IDS[:-1]:
            input_path, _scan, _indexed, input_sha256 = plans_by_input[case_id]
            for arm in driver.ARMS:
                for level in ("full", "summary"):
                    profile_path = root / case_id / f"{level}-{arm}-manifest-profile.json"
                    _write_json(profile_path, {"profile": arm, "level": level})
                    evidence.append(profile_path)
                    profile_manifest.append(
                        {
                            "case": case_id,
                            "input_sha256": input_sha256,
                            "arm": arm,
                            "level": level,
                            "seed": 0,
                            "profile_path": str(profile_path),
                            "workload_fields_validated": True,
                            "timing_fields_semantic": False,
                            "passed": True,
                        }
                    )
        _write_json(
            gate,
            {
                "schema_version": driver.GATE_SCHEMA,
                "status": "passed",
                "admissible": True,
                "input_case_count": 10,
                "admission_case_count": 11,
                "source_commit": "frozen-head",
                "artifacts": {
                    "sim_engine_runtime_path": str(runtime),
                    "sim_engine_runtime_sha256": driver.sha256_file(runtime),
                },
                "raw_files": {str(path): driver.sha256_file(path) for path in evidence},
                "checks": checks,
                "profile_manifest": profile_manifest,
                "cases": gate_cases,
            },
        )
        args = argparse.Namespace(
            run_dir=root / "run",
            semantic_gate=gate,
            plan_map=plan_map,
            stage_binary=binary,
            cpuset="0-7",
            gnu_time=gnu_time,
            taskset=taskset,
        )
        return args, root

    def _prepare(self, directory: str) -> tuple[argparse.Namespace, dict[str, object]]:
        args, _ = self._fixture(directory)
        with (
            patch.object(driver, "_git_head", return_value="frozen-head"),
            patch.object(driver, "_git_tracked_status", return_value=""),
            patch.object(
                driver,
                "_rust_toolchain_identity",
                return_value={
                    "rustup_toolchain": "1.90.0",
                    "rustc_vv": "rustc 1.90.0 (synthetic)",
                    "cargo_version": "cargo 1.90.0 (synthetic)",
                },
            ),
        ):
            manifest = driver.prepare(args)
        return args, manifest

    def test_prepare_freezes_exact_99_cell_matrix_and_all_artifact_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, manifest = self._prepare(directory)

            self.assertEqual(len(manifest["cases"]), 11)
            self.assertEqual(len(manifest["schedule"]), 99)
            self.assertEqual(
                [cell["arm"] for cell in manifest["schedule"][:9]],
                [
                    "scan",
                    "cache",
                    "candidates",
                    "cache",
                    "candidates",
                    "scan",
                    "candidates",
                    "scan",
                    "cache",
                ],
            )
            self.assertEqual({cell["worker_threads"] for cell in manifest["schedule"]}, {1})
            self.assertEqual({tuple(cell["seeds"]) for cell in manifest["schedule"]}, {(0, 1, 7)})
            self.assertEqual(manifest["protocol"]["cell_timeout_seconds"], 30)
            self.assertEqual(manifest["protocol"]["minimum_cell_start_seconds"], 40)
            self.assertEqual(manifest["protocol"]["window_deadline_seconds"], 1200)
            self.assertEqual(
                (args.run_dir / "manifest.sha256").read_text().strip(),
                driver.sha256_file(args.run_dir / "manifest.json"),
            )

    def test_prepare_rejects_gate_plan_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, _ = self._fixture(directory)
            gate = json.loads(args.semantic_gate.read_text())
            gate["cases"]["j35"]["plans"]["scan_sha256"] = "wrong"
            _write_json(args.semantic_gate, gate)

            with (
                patch.object(driver, "_git_head", return_value="frozen-head"),
                patch.object(driver, "_git_tracked_status", return_value=""),
                patch.object(
                    driver,
                    "_rust_toolchain_identity",
                    return_value={
                        "rustup_toolchain": "1.90.0",
                        "rustc_vv": "rustc 1.90.0 (synthetic)",
                        "cargo_version": "cargo 1.90.0 (synthetic)",
                    },
                ),
                self.assertRaisesRegex(ValueError, "scan hash mismatch"),
            ):
                driver.prepare(args)

    def test_prepare_rejects_missing_index_and_nonpreregistered_case_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, root = self._fixture(directory)
            plan_map = json.loads(args.plan_map.read_text())
            indexed = Path(plan_map["cases"][0]["indexed_plan"])
            _write_json(indexed, _plan())
            gate = json.loads(args.semantic_gate.read_text())
            for case_id in ("j35", "j35-full"):
                gate["cases"][case_id]["plans"]["indexed_sha256"] = driver.sha256_file(indexed)
            gate["raw_files"][str(indexed)] = driver.sha256_file(indexed)
            _write_json(args.semantic_gate, gate)
            with self.assertRaisesRegex(ValueError, "lacks resource-dispatch-index/v2"):
                with (
                    patch.object(driver, "_git_head", return_value="frozen-head"),
                    patch.object(driver, "_git_tracked_status", return_value=""),
                ):
                    driver.prepare(args)

        with tempfile.TemporaryDirectory() as directory:
            args, _ = self._fixture(directory)
            plan_map = json.loads(args.plan_map.read_text())
            plan_map["cases"][0], plan_map["cases"][1] = (
                plan_map["cases"][1],
                plan_map["cases"][0],
            )
            _write_json(args.plan_map, plan_map)
            gate = json.loads(args.semantic_gate.read_text())
            gate["raw_files"][str(args.plan_map)] = driver.sha256_file(args.plan_map)
            _write_json(args.semantic_gate, gate)
            with self.assertRaisesRegex(ValueError, "ids or order"):
                with (
                    patch.object(driver, "_git_head", return_value="frozen-head"),
                    patch.object(driver, "_git_tracked_status", return_value=""),
                ):
                    driver.prepare(args)

    def test_prepare_rejects_stage_binary_not_bound_by_semantic_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, root = self._fixture(directory)
            other = root / "other-stage-c-benchmark"
            other.write_bytes(b"different executable")
            other.chmod(0o755)
            args.stage_binary = other
            with (
                patch.object(driver, "_git_head", return_value="frozen-head"),
                patch.object(driver, "_git_tracked_status", return_value=""),
                patch.object(
                    driver,
                    "_rust_toolchain_identity",
                    return_value={
                        "rustup_toolchain": "1.90.0",
                        "rustc_vv": "rustc 1.90.0 (synthetic)",
                        "cargo_version": "cargo 1.90.0 (synthetic)",
                    },
                ),
                self.assertRaisesRegex(ValueError, "not bound"),
            ):
                driver.prepare(args)

    def test_prepare_rejects_missing_full_profile_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, _ = self._fixture(directory)
            gate = json.loads(args.semantic_gate.read_text())
            removed = next(
                index
                for index, record in enumerate(gate["profile_manifest"])
                if record["case"] == "synthetic-dense-affected-n64"
                and record["level"] == "full"
            )
            gate["profile_manifest"].pop(removed)
            _write_json(args.semantic_gate, gate)
            with self.assertRaisesRegex(ValueError, "exactly 60"):
                with (
                    patch.object(driver, "_git_head", return_value="frozen-head"),
                    patch.object(driver, "_git_tracked_status", return_value=""),
                ):
                    driver.prepare(args)

    def test_commands_change_only_plan_and_candidate_dispatch_between_arms(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, manifest = self._prepare(directory)
            case_cells = manifest["schedule"][:3]
            commands = [
                driver._cell_command(
                    manifest, cell, Path(directory) / f"{cell['arm']}.json", Path(directory) / f"{cell['arm']}.time"
                )
                for cell in case_cells
            ]

            self.assertNotIn("--dependency-dispatch", commands[0])
            self.assertNotIn("--dependency-dispatch", commands[1])
            self.assertIn("--dependency-dispatch", commands[2])
            self.assertEqual(commands[0][7], commands[1][7])
            self.assertEqual(commands[1][7], commands[2][7])
            self.assertNotEqual(commands[0][8], commands[1][8])
            self.assertEqual(commands[1][8], commands[2][8])
            for command in commands:
                self.assertEqual(command[:3], [manifest["artifacts"]["taskset"]["path"], "-c", "0-7"])
                self.assertEqual(command[3:6], [manifest["artifacts"]["gnu_time"]["path"], "-v", "-o"])

    def test_report_verification_rejects_dispatch_or_identity_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, manifest = self._prepare(directory)
            cell = manifest["schedule"][0]
            report = self._report(manifest, cell)
            driver._verify_report(manifest, cell, report)
            report["dependency_dispatch"] = True
            with self.assertRaisesRegex(ValueError, "dependency_dispatch"):
                driver._verify_report(manifest, cell, report)

            for field, value in (
                ("samples_sha256", "short"),
                ("batch_result_sha256", "short"),
                ("single_result_bytes", True),
            ):
                with self.subTest(field=field):
                    invalid = self._report(manifest, cell)
                    invalid["records"][0][field] = value
                    with self.assertRaises(ValueError):
                        driver._verify_report(manifest, cell, invalid)
            invalid = self._report(manifest, cell)
            invalid["records"][0]["phases"]["batch_execution_ns"] = -1
            with self.assertRaisesRegex(ValueError, "phase timings"):
                driver._verify_report(manifest, cell, invalid)

    def test_heavy_process_matching_uses_executable_tokens_without_shell_text_false_positive(self) -> None:
        self.assertTrue(driver._is_heavy_process("stage-c-benchma", ["/tmp/stage-c-benchmark"]))
        self.assertTrue(
            driver._is_heavy_process(
                "python3", ["python3", "-m", "pytest", "tests/conformance"]
            )
        )
        self.assertTrue(
            driver._is_heavy_process(
                "python3", ["python3", "/repo/benchmarks/tool/run.py"]
            )
        )
        self.assertFalse(
            driver._is_heavy_process(
                "bash", ["bash", "-lc", "echo stage-c-benchmark pytest cargo"]
            )
        )

    def test_unreadable_host_namespace_is_recorded_without_aborting_snapshot(self) -> None:
        with patch.object(driver.os, "readlink", side_effect=PermissionError("denied")):
            captured = driver._namespace_link("/proc/1/ns/pid")
        self.assertEqual(captured["error_type"], "PermissionError")
        self.assertIn("denied", captured["error"])

    def test_measure_is_once_only_and_uses_fake_process_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, manifest = self._prepare(directory)
            calls = 0

            def fake_capture(command, *, timeout, overlap_check, environment):
                nonlocal calls
                self.assertEqual(timeout, 30)
                self.assertEqual(overlap_check(), [])
                self.assertEqual(environment, {"RUSTUP_TOOLCHAIN": "1.90.0"})
                cell = manifest["schedule"][calls]
                calls += 1
                report_path = Path(command[9])
                time_path = Path(command[6])
                _write_json(report_path, self._report(manifest, cell))
                time_path.write_text(
                    "Maximum resident set size (kbytes): 4096\n"
                    "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:00.01\n",
                    encoding="utf-8",
                )
                return {
                    "command": command,
                    "exit_status": 0,
                    "stdout": "",
                    "stderr": "",
                    "timed_out": False,
                    "overlap": [],
                }

            quiet = {
                "monotonic_ns": 1,
                "hostname": "g-1503-amd128",
                "load_average": [0.0, 0.0, 0.0],
                "logical_cpus": 128,
                "normalized_load_1m": 0.0,
                "process_affinity": list(range(128)),
                "heavy_processes": [],
            }
            measure_args = argparse.Namespace(run_dir=args.run_dir, deadline_seconds=1200)
            with (
                patch.object(driver, "machine_snapshot", return_value=quiet),
                patch.object(driver, "heavy_processes", return_value=[]),
                patch.object(driver, "_run_capture", side_effect=fake_capture),
                patch.object(driver, "_validate_frozen_files", return_value=None),
            ):
                state = driver.measure(measure_args)
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["cells_completed"], 99)
            record = json.loads((args.run_dir / "measurement/cell-000/record.json").read_text())
            self.assertEqual(record["gnu_time"]["maximum_resident_set_kbytes"], 4096)
            with self.assertRaisesRegex(driver.AdmissionError, "once-only"):
                driver.measure(measure_args)

    def test_postflight_after_deadline_is_persisted_as_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            args, manifest = self._prepare(directory)
            calls = 0

            def fake_capture(command, *, timeout, overlap_check, environment):
                nonlocal calls
                cell = manifest["schedule"][calls]
                calls += 1
                _write_json(Path(command[9]), self._report(manifest, cell))
                Path(command[6]).write_text(
                    "Maximum resident set size (kbytes): 1\n", encoding="utf-8"
                )
                return {"exit_status": 0, "stdout": "", "stderr": ""}

            quiet = {
                "hostname": "g-1503-amd128",
                "normalized_load_1m": 0.0,
                "process_affinity": list(range(128)),
                "heavy_processes": [],
            }
            monotonic_calls = 0

            def clock():
                nonlocal monotonic_calls
                monotonic_calls += 1
                return 0.0 if monotonic_calls <= 199 else 1201.0

            with (
                patch.object(driver, "machine_snapshot", return_value=quiet),
                patch.object(driver, "heavy_processes", return_value=[]),
                patch.object(driver, "_run_capture", side_effect=fake_capture),
                patch.object(driver, "_validate_frozen_files", return_value=None),
                patch.object(driver.time, "monotonic", side_effect=clock),
                self.assertRaisesRegex(driver.AdmissionError, "postflight"),
            ):
                driver.measure(argparse.Namespace(run_dir=args.run_dir, deadline_seconds=1200))
            state = json.loads((args.run_dir / "state.json").read_text())
            self.assertEqual(state["status"], "incomplete")
            self.assertIn("deadline_exceeded_during_postflight", state["stop_reason"])

    @staticmethod
    def _report(manifest: dict[str, object], cell: dict[str, object]) -> dict[str, object]:
        case = next(item for item in manifest["cases"] if item["case_id"] == cell["case_id"])
        plan = case["scan_plan"] if cell["arm"] == "scan" else case["indexed_plan"]
        return {
            "schema_version": driver.REPORT_SCHEMA,
            "rustc": "rustc 1.90.0 (synthetic)",
            "plan_path": plan["path"],
            "plan_bytes": plan["bytes"],
            "plan_fingerprint": case["plan_fingerprint"],
            "semantic_profile": case["semantic_profile"],
            "work_policy": plan["work_policy"],
            "rng_profile": plan["rng_profile"],
            "seeds": [0, 1, 7],
            "worker_threads": 1,
            "warmups": 1,
            "repeats": 1,
            "until": None,
            "observation_level": cell["observation_level"],
            "dependency_dispatch": cell["arm"] == "candidates",
            "records": [
                {
                    "repeat": 0,
                    "sample_indexes": [0, 1, 2],
                    "seeds": [0, 1, 7],
                    "samples_sha256": "d" * 64,
                    "batch_result_sha256": "e" * 64,
                    "single_result_bytes": 10,
                    "batch_result_bytes": 20,
                    "phases": {
                        "plan_read_ns": 1,
                        "plan_parse_validate_ns": 2,
                        "fingerprint_ns": 3,
                        "run_state_initialization_ns": 4,
                        "single_sample_execution_ns": 5,
                        "single_sample_serialization_ns": 6,
                        "batch_execution_ns": 7,
                        "batch_serialization_ns": 8,
                        "batch_write_ns": 9,
                        "end_to_end_batch_ns": 10,
                    },
                }
            ],
        }


if __name__ == "__main__":
    unittest.main()
