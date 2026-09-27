"""Bounded controls for the Issue #6 CPU batch baseline harness.

These tests use synthetic manifests and mocked workers.  They do not execute
the formal F35 benchmark window or make a performance claim.
"""

from __future__ import annotations

import argparse
import io
import json
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.cpu_batch_v1 import binding_worker, driver


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _synthetic_plan_identity(path: Path) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "sha256": driver.sha256_file(path),
        "bytes": path.stat().st_size,
        "fingerprint": "synthetic-plan-fingerprint",
        "semantic_profile": driver.EXPECTED_PROFILE,
        "work_policy": driver.EXPECTED_WORK_POLICY,
        "rng_profile": driver.EXPECTED_RNG_PROFILE,
        "duration_minutes": driver.EXPECTED_DURATION,
        "source_inputs_sha256": driver.EXPECTED_SOURCE_DIGEST,
        "resource_dispatch_index_present": False,
    }


def _pyo3_report(
    cell: dict[str, object], seeds: list[int], plan: dict[str, object]
) -> dict[str, object]:
    effective_workers = min(cell["worker_threads"], len(seeds))
    envelope = {
        "plan_fingerprint": plan["fingerprint"],
        "sample_count": len(seeds),
        "worker_threads": effective_workers,
        "until": None,
    }
    proof = {
        "sample_indexes": list(range(len(seeds))),
        "seeds": seeds,
        "samples_sha256": "synthetic-samples",
    }
    return {
        "schema_version": "cpu-batch-binding-cell/v1",
        "plan": {
            key: plan[key]
            for key in (
                "path",
                "sha256",
                "bytes",
                "semantic_profile",
                "work_policy",
                "rng_profile",
                "duration_minutes",
                "source_inputs_sha256",
                "resource_dispatch_index_present",
            )
        },
        "result_envelope": envelope,
        "warmup_envelope": dict(envelope),
        "worker_threads": cell["worker_threads"],
        "effective_worker_threads": effective_workers,
        "sample_count": len(seeds),
        "observation_level": cell["observation_level"],
        "warmups": 1,
        "measured_calls": 1,
        "warmup_completed": True,
        "warmup_matches_measured": True,
        "warmup_proof": dict(proof),
        "proof": proof,
        "call_ns": 10,
        "stages": {},
    }


class CpuBatchBaselineTests(unittest.TestCase):
    def _frozen_run(self, root: Path) -> tuple[Path, dict[str, object], dict[str, object]]:
        run_dir = root / "run"
        run_dir.mkdir()
        seeds_path = run_dir / "seeds-n64.json"
        schedule_path = run_dir / "measurement-list.json"
        _write_json(seeds_path, driver.SEEDS_N64)
        _write_json(schedule_path, driver.measurement_list())

        named_files: dict[str, Path] = {}
        for name in (
            "canonical-input.json",
            "timed-plan.json",
            "reference-plan.json",
            "stage-c-benchmark",
            "sim-engine-runtime",
            "python",
            "runtime-extension.so",
            "Cargo.lock",
            "lineage.json",
            "cell-budget-evidence.json",
        ):
            path = root / name
            path.write_bytes(f"synthetic:{name}".encode())
            named_files[name] = path

        timed_identity: dict[str, object] = {
            "path": str(named_files["timed-plan.json"].resolve()),
            "sha256": driver.sha256_file(named_files["timed-plan.json"]),
            "bytes": named_files["timed-plan.json"].stat().st_size,
            "fingerprint": "synthetic-plan",
            "semantic_profile": driver.EXPECTED_PROFILE,
            "work_policy": driver.EXPECTED_WORK_POLICY,
            "rng_profile": driver.EXPECTED_RNG_PROFILE,
            "source_inputs_sha256": driver.EXPECTED_SOURCE_DIGEST,
            "duration_minutes": driver.EXPECTED_DURATION,
            "phases": ["synthetic-phase"],
            "resource_dispatch_index_present": False,
        }
        reference_identity = dict(timed_identity)
        reference_identity.update(
            {
                "path": str(named_files["reference-plan.json"].resolve()),
                "sha256": driver.sha256_file(named_files["reference-plan.json"]),
                "bytes": named_files["reference-plan.json"].stat().st_size,
                "fingerprint": "synthetic-reference-plan",
                "semantic_profile": "legacy-minute-v1",
            }
        )
        lineage_value = {
            "version": "compiler-lineage/v2",
            "canonical_sha256": driver.EXPECTED_SOURCE_DIGEST,
            "plan_fingerprint": timed_identity["fingerprint"],
        }
        _write_json(named_files["lineage.json"], lineage_value)
        artifacts = {
            key: {"path": str(path.resolve()), "sha256": driver.sha256_file(path)}
            for key, path in {
                "stage_c_benchmark": named_files["stage-c-benchmark"],
                "runtime": named_files["sim-engine-runtime"],
                "python": named_files["python"],
                "pyo3_extension": named_files["runtime-extension.so"],
                "cargo_lock": named_files["Cargo.lock"],
            }.items()
        }
        for key, path in {
            "driver": Path(driver.__file__),
            "binding_worker": Path(binding_worker.__file__),
            "compiler_entrypoint": driver.ROOT / "scripts/compile_ir.py",
        }.items():
            artifacts[key] = {
                "path": str(path.resolve()),
                "sha256": driver.sha256_file(path),
            }
        compiler_argv = [
            "python",
            str((driver.ROOT / "scripts/compile_ir.py").resolve()),
            str(named_files["canonical-input.json"].resolve()),
            str(named_files["timed-plan.json"].resolve()),
            "--semantic-profile",
            driver.EXPECTED_PROFILE,
            "--artifacts-dir",
            str(named_files["lineage.json"].resolve().parent),
        ]
        manifest: dict[str, object] = {
            "schema_version": "cpu-batch-freeze/v1",
            "repository": {"aggregate_sha256": "synthetic-source"},
            "protocol": {
                "path": str(Path(driver.__file__).with_name("PROTOCOL.md").resolve()),
                "sha256": driver.sha256_file(
                    Path(driver.__file__).with_name("PROTOCOL.md")
                ),
            },
            "host": driver.EXPECTED_HOST,
            "cpuset": driver.CPUSET,
            "deadline_seconds": 1200,
            "placement": {"synthetic": "placement"},
            "canonical_input": {
                "path": str(named_files["canonical-input.json"].resolve()),
                "file_sha256": driver.sha256_file(named_files["canonical-input.json"]),
                "semantic_sha256": driver.EXPECTED_SOURCE_DIGEST,
                "project_sha256": driver.EXPECTED_PROJECT_DIGEST,
                "upstream_commit": driver.EXPECTED_UPSTREAM_COMMIT,
            },
            "reference_plan": reference_identity,
            "timed_plan": timed_identity,
            "compiler": {
                "command": " ".join(compiler_argv),
                "argv": compiler_argv,
                "lineage_path": str(named_files["lineage.json"].resolve()),
                "lineage_sha256": driver.sha256_file(named_files["lineage.json"]),
                "lineage_identity": {
                    **lineage_value,
                    "business_fingerprint": None,
                    "core_fingerprint": None,
                },
            },
            "artifacts": artifacts,
            "toolchain": {"python_environment": {"synthetic": "environment"}},
            "schedule": {
                "seeds_path": seeds_path.name,
                "seeds_sha256": driver.sha256_file(seeds_path),
                "measurement_list_path": schedule_path.name,
                "measurement_list_sha256": driver.sha256_file(schedule_path),
                "cell_count": 56,
            },
            "admission_policy": {
                "window_deadline_seconds": 1200,
                "cell_time_budget_seconds": driver.CELL_TIME_BUDGET_SECONDS,
                "postflight_budget_seconds": driver.POSTFLIGHT_BUDGET_SECONDS,
            },
        }
        manifest_path = run_dir / "manifest.json"
        _write_json(manifest_path, manifest)
        (run_dir / "manifest.sha256").write_text(
            driver.sha256_file(manifest_path) + "\n", encoding="ascii"
        )
        return run_dir, manifest, timed_identity

    def test_frozen_seed_sequence_and_rotated_56_cell_schedule_are_exact(self):
        self.assertEqual(driver.SEEDS_N64, [0, 1, 7, 7] * 16)
        self.assertEqual(len(driver.SEEDS_N64), 64)
        schedule = driver.measurement_list()
        self.assertEqual([cell["ordinal"] for cell in schedule], list(range(56)))

        primary = schedule[:48]
        probes = schedule[48:]
        expected_primary = []
        for repeat, workers_order in enumerate(driver.ROTATIONS):
            for workers in workers_order:
                for observation in ("summary", "full"):
                    for backend in ("rust", "pyo3"):
                        expected_primary.append(
                            (repeat, workers, observation, backend, 64)
                        )
        self.assertEqual(
            [
                (
                    cell["repeat"],
                    cell["worker_threads"],
                    cell["observation_level"],
                    cell["backend"],
                    cell["sample_count"],
                )
                for cell in primary
            ],
            expected_primary,
        )
        self.assertEqual(
            [
                (
                    cell["sample_count"],
                    cell["worker_threads"],
                    cell["observation_level"],
                    cell["backend"],
                )
                for cell in probes
            ],
            [
                (count, workers, observation, backend)
                for count, workers in ((1, 1), (8, 8))
                for observation in ("summary", "full")
                for backend in ("rust", "pyo3")
            ],
        )

    def test_load_frozen_rejects_input_plan_binary_source_and_schedule_drift(self):
        cases = (
            "input",
            "plan",
            "reference",
            "protocol",
            "binary",
            "driver",
            "binding_worker",
            "source",
            "seeds",
            "worker",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                run_dir, manifest, timed_identity = self._frozen_run(root)
                source_identity = {"aggregate_sha256": "synthetic-source"}
                identities = {
                    Path(timed_identity["path"]).resolve(): timed_identity,
                    Path(manifest["reference_plan"]["path"]).resolve(): manifest[
                        "reference_plan"
                    ],
                }
                with (
                    patch.object(
                        driver,
                        "plan_identity",
                        side_effect=lambda path, identities=identities: identities[
                            Path(path).resolve()
                        ],
                    ),
                    patch.object(
                        driver, "_git_source_identity", return_value=source_identity
                    ),
                    patch.object(
                        driver,
                        "python_environment_identity",
                        return_value={"synthetic": "environment"},
                    ),
                    patch.object(
                        driver,
                        "EXPECTED_INPUT_FILE_SHA256",
                        manifest["canonical_input"]["file_sha256"],
                    ),
                    patch.object(
                        driver,
                        "EXPECTED_REFERENCE_PLAN_SHA256",
                        manifest["reference_plan"]["sha256"],
                    ),
                    patch.object(
                        driver,
                        "EXPECTED_REFERENCE_PLAN_FINGERPRINT",
                        manifest["reference_plan"]["fingerprint"],
                    ),
                    patch.object(
                        driver,
                        "DEFAULT_REFERENCE_PLAN",
                        Path(manifest["reference_plan"]["path"]),
                    ),
                ):
                    driver.load_frozen(run_dir)
                    if case == "input":
                        Path(manifest["canonical_input"]["path"]).write_bytes(b"changed")
                    elif case == "plan":
                        changed = dict(timed_identity)
                        changed["fingerprint"] = "changed"
                        identities[Path(timed_identity["path"]).resolve()] = changed
                    elif case == "reference":
                        changed = dict(manifest["reference_plan"])
                        changed["fingerprint"] = "old-or-wrong-reference"
                        identities[
                            Path(manifest["reference_plan"]["path"]).resolve()
                        ] = changed
                    elif case == "protocol":
                        manifest["protocol"]["sha256"] = "0" * 64
                    elif case == "binary":
                        Path(manifest["artifacts"]["runtime"]["path"]).write_bytes(
                            b"changed"
                        )
                    elif case in {"driver", "binding_worker"}:
                        manifest["artifacts"][case]["sha256"] = "0" * 64
                    elif case == "source":
                        driver._git_source_identity.return_value = {
                            "aggregate_sha256": "changed"
                        }
                    elif case == "seeds":
                        seeds_path = run_dir / manifest["schedule"]["seeds_path"]
                        _write_json(seeds_path, list(reversed(driver.SEEDS_N64)))
                        manifest["schedule"]["seeds_sha256"] = driver.sha256_file(
                            seeds_path
                        )
                    else:
                        schedule_path = (
                            run_dir / manifest["schedule"]["measurement_list_path"]
                        )
                        schedule = driver.measurement_list()
                        schedule[0]["worker_threads"] = 3
                        _write_json(schedule_path, schedule)
                        manifest["schedule"][
                            "measurement_list_sha256"
                        ] = driver.sha256_file(schedule_path)
                    if case in {
                        "protocol",
                        "driver",
                        "binding_worker",
                        "seeds",
                        "worker",
                    }:
                        manifest_path = run_dir / "manifest.json"
                        _write_json(manifest_path, manifest)
                        (run_dir / "manifest.sha256").write_text(
                            driver.sha256_file(manifest_path) + "\n", encoding="ascii"
                        )
                    with self.assertRaises(RuntimeError):
                        driver.load_frozen(run_dir)

    def test_sealed_gate_rejects_manifest_raw_and_dispatch_drift(self):
        for case in ("missing_seal", "manifest", "raw", "dispatch"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                run_dir = Path(directory) / "run"
                gate_dir = run_dir / "semantic-gate"
                gate_dir.mkdir(parents=True)
                manifest_path = run_dir / "manifest.json"
                _write_json(manifest_path, {"frozen": True})
                plan = run_dir / "timed-plan.json"
                plan.write_bytes(b"synthetic plan")
                raw = gate_dir / "raw.json"
                _write_json(raw, {"evidence": "original"})
                manifest = {
                    "timed_plan": {
                        "path": str(plan),
                        "sha256": driver.sha256_file(plan),
                    }
                }
                report = {
                    "schema_version": "cpu-batch-semantic-gate/v1",
                    "passed": True,
                    "manifest_sha256": driver.sha256_file(manifest_path),
                    "checks": [{"name": "synthetic", "passed": True}],
                    "candidate_dispatch": {
                        "rust_commands_include_flag": False,
                        "pyo3": "unavailable through public run_batch",
                    },
                    "raw_result_files": {
                        raw.name: {
                            "sha256": driver.sha256_file(raw),
                            "bytes": raw.stat().st_size,
                        }
                    },
                }
                report_path = gate_dir / "report.json"
                _write_json(report_path, report)
                seal = gate_dir / "report.sha256"
                seal.write_text(driver.sha256_file(report_path) + "\n", encoding="ascii")
                self.assertTrue(driver.validate_gate_evidence(run_dir, manifest)["passed"])

                if case == "missing_seal":
                    seal.unlink()
                elif case == "manifest":
                    report["manifest_sha256"] = "0" * 64
                    _write_json(report_path, report)
                    seal.write_text(
                        driver.sha256_file(report_path) + "\n", encoding="ascii"
                    )
                elif case == "raw":
                    _write_json(raw, {"evidence": "tampered"})
                else:
                    report["candidate_dispatch"]["rust_commands_include_flag"] = True
                    _write_json(report_path, report)
                    seal.write_text(
                        driver.sha256_file(report_path) + "\n", encoding="ascii"
                    )
                with self.assertRaises(RuntimeError):
                    driver.validate_gate_evidence(run_dir, manifest)

    def test_source_identity_rejects_untracked_added_deleted_or_modified_files(self):
        for status in (
            "?? src/new_runtime.py",
            "A  rust/runtime/src/new.rs",
            " D src/sim_engine_compiler/removed.py",
            " M rust/runtime/src/lib.rs",
        ):
            with (
                self.subTest(status=status),
                patch.object(driver, "checked_output", return_value=status),
                self.assertRaises(RuntimeError),
            ):
                driver._git_source_identity()

    def test_lineage_rejects_wrong_version_canonical_or_plan_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical.json"
            canonical.write_bytes(b"canonical")
            plan = {"fingerprint": "plan-fingerprint"}
            valid = {
                "version": "compiler-lineage/v2",
                "canonical_sha256": driver.EXPECTED_SOURCE_DIGEST,
                "plan_fingerprint": plan["fingerprint"],
            }
            for field, value in (
                ("version", "compiler-lineage/v0"),
                ("canonical_sha256", "wrong-canonical"),
                ("plan_fingerprint", "wrong-plan"),
            ):
                with self.subTest(field=field):
                    lineage = root / f"{field}.json"
                    candidate = dict(valid)
                    candidate[field] = value
                    _write_json(lineage, candidate)
                    with (
                        patch.object(
                            driver,
                            "EXPECTED_INPUT_FILE_SHA256",
                            driver.sha256_file(canonical),
                        ),
                        self.assertRaises(RuntimeError),
                    ):
                        driver.validate_lineage(
                            lineage, plan=plan, input_path=canonical
                        )

    def test_compiler_command_binds_exact_entrypoint_input_plan_and_lineage_dir(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical.json"
            plan = root / "plan.json"
            lineage = root / "artifacts/lineage.json"
            command = " ".join(
                (
                    "python",
                    str((driver.ROOT / "scripts/compile_ir.py").resolve()),
                    str(canonical.resolve()),
                    str(plan.resolve()),
                    "--semantic-profile",
                    driver.EXPECTED_PROFILE,
                    "--artifacts-dir",
                    str(lineage.resolve().parent),
                )
            )
            parsed = driver.validate_compiler_command(
                command,
                input_path=canonical,
                plan_path=plan,
                lineage_path=lineage,
            )
            self.assertIn(str(canonical.resolve()), parsed)
            for replacement in (
                command.replace("compile_ir.py", "compile_execution_plan.py"),
                command.replace(str(canonical.resolve()), str(root / "other.json")),
                command + " --dependency-dispatch",
            ):
                with self.assertRaises(RuntimeError):
                    driver.validate_compiler_command(
                        replacement,
                        input_path=canonical,
                        plan_path=plan,
                        lineage_path=lineage,
                    )

    def test_python_launcher_keeps_virtual_environment_symlink_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            global_python = root / "global-python"
            global_python.write_bytes(b"synthetic interpreter")
            launcher = root / ".venv/bin/python"
            launcher.parent.mkdir(parents=True)
            launcher.symlink_to(global_python)
            admitted = driver._require_python_path(launcher)
            self.assertEqual(admitted, launcher.absolute())
            self.assertNotEqual(admitted, launcher.resolve())

    def test_python_environment_identity_works_without_pip_and_keeps_venv_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            venv = Path(directory) / "venv"
            subprocess.run(
                [sys.executable, "-m", "venv", "--without-pip", str(venv)],
                check=True,
                capture_output=True,
            )
            launcher = venv / "bin/python"
            self.assertTrue(launcher.is_symlink())
            identity = driver.python_environment_identity(launcher)
        self.assertEqual(Path(identity["metadata"]["prefix"]), venv)
        self.assertNotEqual(
            identity["metadata"]["prefix"], identity["metadata"]["base_prefix"]
        )
        self.assertIsInstance(identity["installed_distributions"], list)

    def test_placement_rejects_affinity_core_numa_and_smt_drift(self):
        def topology(*, duplicate_core=False, split_numa=False, omit_sibling=False):
            rows = []
            for cpu in range(8):
                core = 0 if duplicate_core and cpu == 1 else cpu
                node = 1 if split_numa and cpu == 7 else 0
                rows.append(f"{cpu},{core},0,{node}")
                if not (omit_sibling and cpu == 7):
                    rows.append(f"{cpu + 64},{core},0,{node}")
            return "\n".join(rows)

        with (
            patch.object(driver.os, "sched_getaffinity", return_value=set(range(128))),
            patch.object(driver, "checked_output", return_value=topology()),
        ):
            placement = driver.validate_placement()
        self.assertEqual(placement["selected_logical_cpus"], list(range(8)))
        self.assertEqual(placement["numa_nodes"], [0])
        self.assertEqual(json.loads(json.dumps(placement)), placement)

        cases = (
            (set(range(7)), topology()),
            (set(range(128)), topology(duplicate_core=True)),
            (set(range(128)), topology(split_numa=True)),
            (set(range(128)), topology(omit_sibling=True)),
        )
        for affinity, output in cases:
            with (
                self.subTest(affinity=len(affinity), output=output[-20:]),
                patch.object(driver.os, "sched_getaffinity", return_value=affinity),
                patch.object(driver, "checked_output", return_value=output),
                self.assertRaises(RuntimeError),
            ):
                driver.validate_placement()

    def test_measure_reserves_frozen_cell_budget_and_cannot_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            run_dir.mkdir()
            _write_json(run_dir / "seeds-n64.json", driver.SEEDS_N64)
            _write_json(run_dir / "measurement-list.json", driver.measurement_list())
            manifest = {
                "placement": {"synthetic": "placement"},
                "admission_policy": {
                    "window_deadline_seconds": 1200,
                    "cell_time_budget_seconds": driver.CELL_TIME_BUDGET_SECONDS,
                    "postflight_budget_seconds": driver.POSTFLIGHT_BUDGET_SECONDS,
                },
                "schedule": {
                    "seeds_path": "seeds-n64.json",
                    "measurement_list_path": "measurement-list.json",
                }
            }
            args = argparse.Namespace(
                run_dir=run_dir, deadline_seconds=1200, minimum_start_seconds=0
            )
            with (
                patch.object(driver, "load_frozen", return_value=manifest),
                patch.object(driver, "validate_gate_evidence", return_value={}),
                patch.object(
                    driver,
                    "validate_placement",
                    return_value={"synthetic": "placement"},
                ),
            ):
                with (
                    patch.object(driver, "machine_snapshot", return_value={}),
                    patch.object(driver.time, "monotonic", side_effect=(0.0, 1131.0)),
                    patch.object(
                        driver.time,
                        "monotonic_ns",
                        side_effect=(0, 1_131_000_000_000),
                    ),
                    patch.object(driver, "_run_capture") as run_capture,
                ):
                    state = driver.measure(args)
                run_capture.assert_not_called()
                self.assertEqual(state["status"], "incomplete")
                self.assertEqual(
                    state["stop_reason"],
                    "remaining_window_below_frozen_cell_plus_postflight_budget",
                )
                self.assertEqual(state["cells_completed"], 0)
                with self.assertRaises(FileExistsError):
                    driver.measure(args)

    def test_measure_cli_rejects_a_deadline_above_twenty_minutes(self):
        with (
            patch.object(
                sys,
                "argv",
                [
                    "cpu-batch-driver",
                    "measure",
                    "--run-dir",
                    "/not-used",
                    "--deadline-seconds",
                    "1200.001",
                ],
            ),
            patch("sys.stderr", new=io.StringIO()),
            patch.object(driver, "measure") as measure,
            self.assertRaises(SystemExit) as raised,
        ):
            driver.main()
        self.assertEqual(raised.exception.code, 2)
        measure.assert_not_called()

    def test_measure_rechecks_frozen_placement_before_creating_window(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            manifest = {
                "placement": {"selected_logical_cpus": list(range(8))},
            }
            with (
                patch.object(driver, "load_frozen", return_value=manifest),
                patch.object(driver, "validate_gate_evidence", return_value={}),
                patch.object(
                    driver,
                    "validate_placement",
                    return_value={"selected_logical_cpus": list(range(1, 9))},
                ),
                self.assertRaises(RuntimeError),
            ):
                driver.measure(
                    argparse.Namespace(
                        run_dir=run_dir,
                        deadline_seconds=1200,
                        minimum_start_seconds=0,
                    )
                )
            self.assertFalse((run_dir / "measurement").exists())

    def test_invalid_cell_json_persists_failed_record_and_closes_window(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            run_dir.mkdir()
            seeds_path = run_dir / "seeds.json"
            schedule_path = run_dir / "schedule.json"
            plan = run_dir / "plan.json"
            python = run_dir / "python"
            plan.write_bytes(b"plan")
            python.write_bytes(b"python")
            _write_json(seeds_path, driver.SEEDS_N64)
            cell = {
                "ordinal": 0,
                "kind": "primary",
                "repeat": 0,
                "sample_count": 64,
                "worker_threads": 1,
                "observation_level": "summary",
                "backend": "pyo3",
                "warmups": 1,
                "measured_calls": 1,
            }
            _write_json(schedule_path, [cell])
            placement = {"synthetic": "placement"}
            manifest = {
                "placement": placement,
                "admission_policy": {
                    "window_deadline_seconds": 1200,
                    "cell_time_budget_seconds": driver.CELL_TIME_BUDGET_SECONDS,
                    "postflight_budget_seconds": driver.POSTFLIGHT_BUDGET_SECONDS,
                },
                "schedule": {
                    "seeds_path": seeds_path.name,
                    "measurement_list_path": schedule_path.name,
                },
                "timed_plan": {"path": str(plan)},
                "artifacts": {"python": {"path": str(python)}},
            }

            def invalid_report(command, cwd, timeout=None, environment=None):
                del cwd
                report_path = Path(command[command.index("--report") + 1])
                report_path.write_text("{invalid json", encoding="utf-8")
                self.assertEqual(timeout, driver.CELL_TIME_BUDGET_SECONDS)
                self.assertEqual(environment["LC_ALL"], "C")
                return {
                    "command": command,
                    "started_monotonic_ns": 1,
                    "finished_monotonic_ns": 2,
                    "wall_ns": 1,
                    "exit_status": 0,
                    "stdout": "synthetic stdout",
                    "stderr": "synthetic stderr",
                    "timed_out": False,
                }

            with (
                patch.object(driver, "load_frozen", return_value=manifest),
                patch.object(driver, "validate_gate_evidence", return_value={}),
                patch.object(driver, "validate_placement", return_value=placement),
                patch.object(driver, "validate_execution_artifacts", return_value=None),
                patch.object(driver, "machine_snapshot", return_value={}),
                patch.object(driver.time, "monotonic", return_value=0.0),
                patch.object(driver.time, "monotonic_ns", side_effect=(0, 1)),
                patch.object(driver, "_run_capture", side_effect=invalid_report),
            ):
                state = driver.measure(
                    argparse.Namespace(
                        run_dir=run_dir,
                        deadline_seconds=1200,
                        minimum_start_seconds=0,
                    )
                )

            record_path = run_dir / "measurement/cell-00/record.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertEqual(record["status"], "failed")
            self.assertEqual(record["failure"]["type"], "JSONDecodeError")
            self.assertEqual(state["status"], "incomplete")
            self.assertEqual(state["stop_reason"], "cell_evidence_invalid:0")
            self.assertEqual(state["cells_completed"], 0)
            self.assertEqual(state["incomplete_ordinals"], [])
            self.assertIn("raw_report", record)
            self.assertIn("stdout", record["captured_output"])
            self.assertIn("stderr", record["captured_output"])

    def test_gnu_time_parser_accepts_frozen_c_locale_labels(self):
        parsed = driver.parse_gnu_time(
            "Maximum resident set size (kbytes): 4096\n"
            "Elapsed (wall clock) time (h:mm:ss or m:ss): 0:01.25\n"
        )
        self.assertEqual(parsed["maximum_resident_set_kbytes"], 4096)
        self.assertEqual(parsed["elapsed_wall"], "0:01.25")

    def test_nonempty_divergence_is_json_safe_and_preserves_path_and_values(self):
        exact = driver._first_divergence({"metric": 1}, {"metric": 2})
        encoded = driver._jsonable_divergence(exact)
        self.assertEqual(encoded["path"], "root.metric")
        self.assertEqual(encoded["expected"], 1)
        self.assertEqual(encoded["actual"], 2)
        self.assertEqual(json.loads(json.dumps(encoded)), encoded)
        self.assertEqual(binding_worker._jsonable_divergence(exact), encoded)

        tiny = driver._first_divergence(
            {"metric": 1.0}, {"metric": 1.0 + 1e-15}
        )
        accepted = driver._first_divergence(
            {"metric": 1.0},
            {"metric": 1.0 + 1e-15},
            accepted_reference=True,
        )
        self.assertIsNotNone(tiny)
        self.assertIsNone(accepted)
        json.dumps(driver._jsonable_divergence(tiny), allow_nan=False)

    @unittest.skipUnless(hasattr(signal, "SIGINT"), "POSIX signal control required")
    def test_run_capture_interrupt_kills_only_owned_child_session(self):
        sentinel = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            start_new_session=True,
        )
        child = (
            "import os,signal,subprocess,sys,time;"
            "grand=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)']);"
            "print(grand.pid,flush=True);time.sleep(0.05);"
            "os.kill(os.getppid(),signal.SIGINT);time.sleep(10)"
        )
        try:
            with self.assertRaises(driver.CellProcessInterrupted) as raised:
                driver._run_capture(
                    [sys.executable, "-c", child], Path.cwd(), timeout=5
                )
            execution = raised.exception.execution
            self.assertTrue(execution["interrupted"])
            self.assertTrue(execution["process_group_killed"])
            self.assertRegex(execution["stdout"].strip(), r"^\d+$")
            grandchild = int(execution["stdout"].strip())
            state = None
            for _ in range(50):
                stat = Path(f"/proc/{grandchild}/stat")
                if not stat.exists():
                    break
                state = stat.read_text(encoding="ascii").split()[2]
                if state == "Z":
                    break
                time.sleep(0.02)
            self.assertIn(state, (None, "Z"))
            self.assertIsNone(sentinel.poll())
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=5)

    def test_measure_persists_sigint_and_sigterm_and_restores_handlers(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as directory:
                run_dir = Path(directory) / "run"
                run_dir.mkdir()
                seeds_path = run_dir / "seeds.json"
                schedule_path = run_dir / "schedule.json"
                plan = run_dir / "plan.json"
                python = run_dir / "python"
                plan.write_bytes(b"plan")
                python.write_bytes(b"python")
                _write_json(seeds_path, driver.SEEDS_N64)
                cell = {
                    "ordinal": 0,
                    "kind": "primary",
                    "repeat": 0,
                    "sample_count": 1,
                    "worker_threads": 1,
                    "observation_level": "summary",
                    "backend": "pyo3",
                    "warmups": 1,
                    "measured_calls": 1,
                }
                _write_json(schedule_path, [cell])
                placement = {"synthetic": "placement"}
                manifest = {
                    "placement": placement,
                    "admission_policy": {
                        "window_deadline_seconds": 1200,
                        "cell_time_budget_seconds": driver.CELL_TIME_BUDGET_SECONDS,
                        "postflight_budget_seconds": driver.POSTFLIGHT_BUDGET_SECONDS,
                    },
                    "schedule": {
                        "seeds_path": seeds_path.name,
                        "measurement_list_path": schedule_path.name,
                    },
                    "timed_plan": {"path": str(plan)},
                    "artifacts": {"python": {"path": str(python)}},
                }
                before = {
                    item: signal.getsignal(item)
                    for item in (signal.SIGINT, signal.SIGTERM)
                }

                def interrupt(*_args, signum=signum, **_kwargs):
                    try:
                        signal.raise_signal(signum)
                    except KeyboardInterrupt as error:
                        raise driver.CellProcessInterrupted(
                            {
                                "command": ["synthetic"],
                                "started_monotonic_ns": 1,
                                "finished_monotonic_ns": 2,
                                "wall_ns": 1,
                                "exit_status": None,
                                "stdout": "partial stdout",
                                "stderr": "partial stderr",
                                "timed_out": False,
                                "interrupted": True,
                                "process_group_killed": True,
                            }
                        ) from error

                with (
                    patch.object(driver, "load_frozen", return_value=manifest),
                    patch.object(driver, "validate_gate_evidence", return_value={}),
                    patch.object(driver, "validate_placement", return_value=placement),
                    patch.object(
                        driver, "validate_execution_artifacts", return_value=None
                    ),
                    patch.object(driver, "machine_snapshot", return_value={}),
                    patch.object(driver.time, "monotonic", return_value=0.0),
                    patch.object(driver.time, "monotonic_ns", side_effect=(0, 1)),
                    patch.object(driver, "_run_capture", side_effect=interrupt),
                ):
                    state = driver.measure(
                        argparse.Namespace(
                            run_dir=run_dir,
                            deadline_seconds=1200,
                            minimum_start_seconds=0,
                        )
                    )

                record = json.loads(
                    (run_dir / "measurement/cell-00/record.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertEqual(record["status"], "failed")
                self.assertEqual(record["failure"]["type"], "coordinator_interrupt")
                self.assertEqual(record["failure"]["signal"], signum)
                self.assertEqual(state["status"], "incomplete")
                self.assertEqual(state["stop_reason"], f"coordinator_interrupt:{signum}")
                self.assertEqual(state["incomplete_ordinals"], [])
                self.assertEqual(
                    {item: signal.getsignal(item) for item in before}, before
                )

    def test_signal_during_machine_before_is_persisted_and_handlers_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            run_dir.mkdir()
            seeds_path = run_dir / "seeds.json"
            schedule_path = run_dir / "schedule.json"
            _write_json(seeds_path, driver.SEEDS_N64)
            _write_json(schedule_path, [driver.measurement_list()[0]])
            placement = {"synthetic": "placement"}
            manifest = {
                "placement": placement,
                "admission_policy": {
                    "window_deadline_seconds": 1200,
                    "cell_time_budget_seconds": driver.CELL_TIME_BUDGET_SECONDS,
                    "postflight_budget_seconds": driver.POSTFLIGHT_BUDGET_SECONDS,
                },
                "schedule": {
                    "seeds_path": seeds_path.name,
                    "measurement_list_path": schedule_path.name,
                },
            }
            before = {
                item: signal.getsignal(item)
                for item in (signal.SIGINT, signal.SIGTERM)
            }
            snapshots = 0

            def interrupt_first_snapshot(**_kwargs):
                nonlocal snapshots
                snapshots += 1
                if snapshots == 1:
                    signal.raise_signal(signal.SIGTERM)
                return {}

            with (
                patch.object(driver, "load_frozen", return_value=manifest),
                patch.object(driver, "validate_gate_evidence", return_value={}),
                patch.object(driver, "validate_placement", return_value=placement),
                patch.object(
                    driver, "machine_snapshot", side_effect=interrupt_first_snapshot
                ),
                patch.object(driver.time, "monotonic", return_value=0.0),
                patch.object(driver.time, "monotonic_ns", side_effect=(0, 1)),
                patch.object(driver, "_run_capture") as run_capture,
            ):
                state = driver.measure(
                    argparse.Namespace(
                        run_dir=run_dir,
                        deadline_seconds=1200,
                        minimum_start_seconds=0,
                    )
                )

            run_capture.assert_not_called()
            self.assertEqual(state["status"], "incomplete")
            self.assertEqual(
                state["stop_reason"], f"coordinator_interrupt:{signal.SIGTERM}"
            )
            self.assertEqual(state["incomplete_ordinals"], [0])
            self.assertEqual(
                {item: signal.getsignal(item) for item in before}, before
            )

    def test_invalid_sample_indexes_or_seed_order_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_bytes(b"synthetic plan")
            frozen_plan = _synthetic_plan_identity(plan_path)
            cell = {
                "backend": "pyo3",
                "observation_level": "summary",
                "worker_threads": 1,
            }
            seeds = [7, 0, 7, 1]
            valid = _pyo3_report(cell, seeds, frozen_plan)
            for field, wrong in (
                ("sample_indexes", [0, 2, 1, 3]),
                ("seeds", [7, 7, 0, 1]),
            ):
                with self.subTest(field=field):
                    report = json.loads(json.dumps(valid))
                    report["proof"][field] = wrong
                    with self.assertRaises(AssertionError):
                        driver._verify_cell_report(
                            cell, seeds, report, frozen_plan
                        )

    def test_rust_and_pyo3_cell_reports_reject_identity_field_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            plan_path = Path(directory) / "plan.json"
            plan_path.write_bytes(b"synthetic plan")
            frozen_plan = _synthetic_plan_identity(plan_path)
            seeds = [7, 0, 7, 1]
            rust_cell = {
                "backend": "rust",
                "observation_level": "summary",
                "worker_threads": 8,
            }
            rust = {
                "schema_version": "stage-c-segmented-benchmark/v1",
                "plan_path": frozen_plan["path"],
                "plan_bytes": frozen_plan["bytes"],
                "plan_fingerprint": frozen_plan["fingerprint"],
                "semantic_profile": frozen_plan["semantic_profile"],
                "work_policy": frozen_plan["work_policy"],
                "rng_profile": frozen_plan["rng_profile"],
                "seeds": seeds,
                "worker_threads": 4,
                "warmups": 1,
                "repeats": 1,
                "until": None,
                "observation_level": "summary",
                "dependency_dispatch": False,
                "records": [
                    {
                        "repeat": 0,
                        "sample_indexes": [0, 1, 2, 3],
                        "seeds": seeds,
                        "samples_sha256": "rust-only-digest",
                        "phases": {"batch_execution_ns": 10},
                    }
                ],
            }
            driver._verify_cell_report(rust_cell, seeds, rust, frozen_plan)
            rust_mutations = {
                "schema_version": "stage-c-segmented-benchmark/v0",
                "plan_path": "/wrong/plan",
                "plan_bytes": 1,
                "plan_fingerprint": "wrong",
                "semantic_profile": "wrong",
                "work_policy": "wrong",
                "rng_profile": "wrong",
                "seeds": list(reversed(seeds)),
                "worker_threads": 1,
                "warmups": 2,
                "repeats": 2,
                "until": 1,
                "observation_level": "full",
                "dependency_dispatch": True,
            }
            for field, wrong in rust_mutations.items():
                with self.subTest(backend="rust", field=field):
                    report = json.loads(json.dumps(rust))
                    report[field] = wrong
                    with self.assertRaises(AssertionError):
                        driver._verify_cell_report(
                            rust_cell, seeds, report, frozen_plan
                        )

            pyo3_cell = dict(rust_cell, backend="pyo3")
            pyo3 = _pyo3_report(pyo3_cell, seeds, frozen_plan)
            pyo3["proof"]["samples_sha256"] = "pyo3-only-digest"
            driver._verify_cell_report(pyo3_cell, seeds, pyo3, frozen_plan)
            mutations = (
                ("plan", "path", "/wrong/plan"),
                ("plan", "sha256", "wrong"),
                ("plan", "bytes", 1),
                ("plan", "semantic_profile", "wrong"),
                ("plan", "work_policy", "wrong"),
                ("plan", "rng_profile", "wrong"),
                ("result_envelope", "plan_fingerprint", "wrong"),
                ("result_envelope", "sample_count", 3),
                ("result_envelope", "worker_threads", 1),
                ("result_envelope", "until", 1),
                ("warmup_envelope", "until", 1),
                (None, "schema_version", "cpu-batch-binding-cell/v0"),
                (None, "worker_threads", 1),
                (None, "observation_level", "full"),
                (None, "sample_count", 3),
                (None, "warmups", 2),
                (None, "measured_calls", 2),
            )
            for section, field, wrong in mutations:
                with self.subTest(backend="pyo3", section=section, field=field):
                    report = json.loads(json.dumps(pyo3))
                    target = report if section is None else report[section]
                    target[field] = wrong
                    with self.assertRaises(AssertionError):
                        driver._verify_cell_report(
                            pyo3_cell, seeds, report, frozen_plan
                        )

    def test_partial_summary_keeps_groups_separate_and_reports_missing_cells(self):
        def record(
            ordinal: int,
            backend: str,
            observation: str,
            workers: int,
            repeat: int,
            duration: int,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "cell": {
                    "ordinal": ordinal,
                    "kind": "primary",
                    "backend": backend,
                    "observation_level": observation,
                    "worker_threads": workers,
                    "repeat": repeat,
                },
                "proof": {"warm_batch_ns": duration},
                "gnu_time": {"maximum_resident_set_kbytes": 100 + ordinal},
            }

        records = [
            record(0, "rust", "summary", 1, 0, 100),
            record(1, "rust", "summary", 2, 0, 50),
            record(2, "rust", "full", 1, 0, 1_000),
            record(3, "rust", "full", 2, 0, 1_000),
            record(4, "pyo3", "summary", 1, 0, 200),
            record(5, "pyo3", "summary", 2, 0, 100),
            {
                "status": "failed",
                "cell": {"ordinal": 6, "kind": "primary"},
                "failure": "synthetic failure",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            measurement = run_dir / "measurement"
            for item in records:
                cell_dir = measurement / f"cell-{item['cell']['ordinal']:02d}"
                target = cell_dir / "record.json"
                if item["status"] == "completed":
                    raw_path = cell_dir / "raw-report.json"
                    _write_json(
                        raw_path,
                        (
                            {"records": [{"phases": {}}]}
                            if item["cell"]["backend"] == "rust"
                            else {"stages": {}}
                        ),
                    )
                    item["raw_report"] = {"path": raw_path.name}
                _write_json(target, item)
            _write_json(
                measurement / "state.json",
                {"status": "incomplete", "cells_completed": 6},
            )
            manifest_path = run_dir / "manifest.json"
            _write_json(manifest_path, {})
            with (
                patch.object(driver, "load_frozen", return_value={}),
                patch.object(
                    driver,
                    "validate_measurement_records",
                    return_value=(
                        {"status": "incomplete", "cells_completed": 6},
                        records,
                    ),
                ),
            ):
                summary = driver.summarize(argparse.Namespace(run_dir=run_dir))

        self.assertEqual(summary["measurement_status"], "incomplete")
        self.assertFalse(summary["complete_issue6_baseline"])
        self.assertEqual(summary["cells_completed"], 6)
        self.assertEqual(summary["cells_failed"], 1)
        self.assertEqual(summary["cells_missing"], 49)
        rows = {
            (row["backend"], row["observation_level"], row["worker_threads"]): row
            for row in summary["primary"]
        }
        self.assertEqual(len(rows), 6)
        self.assertEqual(
            rows[("rust", "summary", 2)][
                "paired_speedup_vs_same_repeat_worker_1"
            ]["median"],
            2.0,
        )
        self.assertEqual(
            rows[("rust", "full", 2)][
                "paired_speedup_vs_same_repeat_worker_1"
            ]["median"],
            1.0,
        )
        self.assertEqual(
            rows[("pyo3", "summary", 2)][
                "paired_speedup_vs_same_repeat_worker_1"
            ]["median"],
            2.0,
        )
        self.assertTrue(all(row["repeat_count"] == 1 for row in rows.values()))
        limitations = " ".join(summary["limitations"])
        self.assertIn("warmup and measured result trees", limitations)
        self.assertIn("proof construction", limitations)
        self.assertIn("wrapper encoding", limitations)
        self.assertIn("must not form an incremental-memory ratio", limitations)

    def test_summary_validation_rejects_cell_and_evidence_drift(self):
        for case in ("directory", "ordinal", "stdout", "stderr", "raw"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                run_dir = Path(directory) / "run"
                measure_dir = run_dir / "measurement"
                cell_dir = measure_dir / "cell-00"
                cell_dir.mkdir(parents=True)
                seeds_path = run_dir / "seeds.json"
                schedule_path = run_dir / "schedule.json"
                _write_json(seeds_path, driver.SEEDS_N64)
                cell = {
                    "ordinal": 0,
                    "kind": "primary",
                    "repeat": 0,
                    "sample_count": 1,
                    "worker_threads": 1,
                    "observation_level": "summary",
                    "backend": "pyo3",
                    "warmups": 1,
                    "measured_calls": 1,
                }
                _write_json(schedule_path, [cell])
                plan = run_dir / "plan.json"
                python = run_dir / "python"
                plan.write_bytes(b"plan")
                python.write_bytes(b"python")
                frozen_plan = _synthetic_plan_identity(plan)
                manifest = {
                    "schedule": {
                        "seeds_path": seeds_path.name,
                        "measurement_list_path": schedule_path.name,
                    },
                    "timed_plan": frozen_plan,
                    "artifacts": {"python": {"path": str(python)}},
                }
                raw = _pyo3_report(cell, [0], frozen_plan)
                raw_path = cell_dir / "raw-report.json"
                stdout = cell_dir / "stdout.txt"
                stderr = cell_dir / "stderr.txt"
                _write_json(raw_path, raw)
                stdout.write_text("stdout", encoding="utf-8")
                stderr.write_text("stderr", encoding="utf-8")
                proof = driver._verify_cell_report(cell, [0], raw, frozen_plan)
                record = {
                    "status": "completed",
                    "cell": cell,
                    "command": driver._cell_command(manifest, cell, [0], raw_path),
                    "proof": proof,
                    "captured_output": {
                        name: {
                            "path": path.name,
                            "sha256": driver.sha256_file(path),
                            "bytes": path.stat().st_size,
                        }
                        for name, path in (("stdout", stdout), ("stderr", stderr))
                    },
                    "raw_report": {
                        "path": raw_path.name,
                        "sha256": driver.sha256_file(raw_path),
                        "bytes": raw_path.stat().st_size,
                    },
                }
                record_path = cell_dir / "record.json"
                _write_json(record_path, record)
                _write_json(
                    measure_dir / "state.json",
                    {"status": "incomplete", "cells_completed": 1},
                )
                driver.validate_measurement_records(run_dir, manifest)

                if case == "directory":
                    cell_dir.rename(measure_dir / "cell-01")
                elif case == "ordinal":
                    record["cell"] = dict(cell, ordinal=1)
                    _write_json(record_path, record)
                elif case == "stdout":
                    stdout.write_text("changed stdout", encoding="utf-8")
                elif case == "stderr":
                    stderr.write_text("changed stderr", encoding="utf-8")
                else:
                    _write_json(raw_path, {"changed": True})
                with self.assertRaises(RuntimeError):
                    driver.validate_measurement_records(run_dir, manifest)

    def test_completed_state_requires_every_preregistered_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory) / "run"
            measure_dir = run_dir / "measurement"
            measure_dir.mkdir(parents=True)
            seeds_path = run_dir / "seeds.json"
            schedule_path = run_dir / "schedule.json"
            _write_json(seeds_path, driver.SEEDS_N64)
            _write_json(schedule_path, driver.measurement_list())
            _write_json(
                measure_dir / "state.json",
                {"status": "completed", "cells_completed": 0},
            )
            manifest = {
                "schedule": {
                    "seeds_path": seeds_path.name,
                    "measurement_list_path": schedule_path.name,
                }
            }
            with self.assertRaises(RuntimeError):
                driver.validate_measurement_records(run_dir, manifest)

    def test_binding_report_keeps_unsupported_stage_values_null(self):
        calls = []
        fingerprint = "synthetic-plan-fingerprint"

        def run_batch(plan, seeds, *, worker_threads, observation_level):
            calls.append((plan, list(seeds), worker_threads, observation_level))
            return {
                "plan_fingerprint": fingerprint,
                "sample_count": len(seeds),
                "worker_threads": min(worker_threads, len(seeds)),
                "until": None,
                "samples": [
                    {
                        "sample_index": index,
                        "seed": seed,
                        "result": {
                            "trace": [],
                            "plan_fingerprint": fingerprint,
                        },
                    }
                    for index, seed in enumerate(seeds)
                ]
            }

        fake_binding = types.SimpleNamespace(
            native_available=lambda: True, run_batch=run_batch
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / "plan.json"
            _write_json(
                plan,
                {
                    "semantic_profile": driver.EXPECTED_PROFILE,
                    "work_policy": driver.EXPECTED_WORK_POLICY,
                    "rng_profile": driver.EXPECTED_RNG_PROFILE,
                    "duration_minutes": driver.EXPECTED_DURATION,
                    "source_inputs_sha256": driver.EXPECTED_SOURCE_DIGEST,
                },
            )
            report_path = root / "report.json"
            with patch.dict(sys.modules, {"sim_engine_compiler": fake_binding}):
                report = binding_worker.run_cell(
                    plan, [7, 0, 7, 1], 1, "summary", report_path
                )

        self.assertEqual(len(calls), 2)
        for stage in (
            "canonical_compilation_ns",
            "batch_only_initialization_ns",
            "batch_only_execution_ns",
            "independent_in_process_end_to_end_ns",
        ):
            self.assertIsNone(report["stages"][stage])
        self.assertGreater(report["call_ns"], 0)


if __name__ == "__main__":
    unittest.main()
