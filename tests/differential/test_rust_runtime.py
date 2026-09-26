from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rust" / "runtime" / "Cargo.toml"
F35 = ROOT / "tests" / "fixtures" / "spare_mvp" / "f35-43day-5352a0d"
SYNTHETIC = (
    "b1",
    "b2-failure-repair",
    "b2-preventive-maintenance",
    "b3-upstream-transport",
)
NON_TRACE_RESULT_FIELDS = (
    "plan_fingerprint",
    "seed",
    "time",
    "stop_reason",
    "sample_requests",
    "metrics",
    "terminal_state",
)


def _cargo() -> str:
    found = shutil.which("cargo")
    if found:
        return found
    rustup_default = Path.home() / ".cargo" / "bin" / "cargo"
    if rustup_default.exists():
        return str(rustup_default)
    raise AssertionError("Rust conformance requires cargo; install the pinned rust-toolchain.toml toolchain")


class RustRuntimeConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [_cargo(), "build", "--quiet", "--release", "--manifest-path", str(MANIFEST)],
            cwd=ROOT,
            check=True,
        )
        executable = "sim-engine-runtime.exe" if __import__("os").name == "nt" else "sim-engine-runtime"
        cls.binary = ROOT / "rust" / "runtime" / "target" / "release" / executable
        cls.tempdir = tempfile.TemporaryDirectory(prefix="sim-engine-rust-conformance-")

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def _run_rust(
        self,
        plan_path: Path,
        seed: int,
        observation_level: str = "full",
        until: int | None = None,
    ) -> dict:
        output = (
            Path(self.tempdir.name)
            / f"{plan_path.stem}-{seed}-{observation_level}-{until}.json"
        )
        command = [
            str(self.binary),
            str(plan_path),
            str(output),
            "--seed",
            str(seed),
            "--observation-level",
            observation_level,
        ]
        if until is not None:
            command.extend(("--until", str(until)))
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())

    def _run_rust_batch(
        self,
        plan_path: Path,
        seeds: tuple[int, ...],
        worker_threads: int,
        observation_level: str = "full",
        until: int | None = None,
    ) -> dict:
        suffix = "-".join(str(seed) for seed in seeds)
        output = (
            Path(self.tempdir.name)
            / f"{plan_path.stem}-batch-{worker_threads}-{observation_level}-{until}-{suffix}.json"
        )
        command = [
            str(self.binary),
            str(plan_path),
            str(output),
            "--seeds",
            ",".join(str(seed) for seed in seeds),
            "--worker-threads",
            str(worker_threads),
            "--observation-level",
            observation_level,
        ]
        if until is not None:
            command.extend(("--until", str(until)))
        subprocess.run(
            command,
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())

    def assert_observation_equivalent(self, full: dict, summary: dict):
        self.assertEqual(summary["trace"], [])
        for field in NON_TRACE_RESULT_FIELDS:
            self.assertEqual(summary[field], full[field], field)

    def test_synthetic_slices_match_saved_python_results(self):
        for name in SYNTHETIC:
            with self.subTest(case=name):
                prefix = "b1" if name == "b1" else name
                plan_path = ROOT / "tests" / "fixtures" / "synthetic" / f"{prefix}-execution-plan.json"
                expected_path = ROOT / "tests" / "fixtures" / "synthetic" / f"{prefix}-reference-result.json"
                expected = json.loads(expected_path.read_text())
                full = self._run_rust(plan_path, 0, "full")
                summary = self._run_rust(plan_path, 0, "summary")
                self.assertIsNone(first_divergence(expected, full))
                self.assert_observation_equivalent(full, summary)

    def test_f35_required_seeds_match_python_reference_full_result(self):
        plan_path = F35 / "execution-plan.json"
        plan = ExecutionPlan.from_dict(json.loads(plan_path.read_text()))
        for seed in (0, 1, 7):
            with self.subTest(seed=seed):
                expected = SimpyReferenceRuntime(plan, seed=seed).run()
                actual = self._run_rust(plan_path, seed)
                self.assertIsNone(
                    first_divergence(
                        expected,
                        actual,
                        float_rel_tol=2e-15,
                        float_abs_tol=1e-12,
                    )
                )

    def test_aircraft_cli_preserves_full_unsigned_seed_range(self):
        plan_path = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
        result = self._run_rust(plan_path, 2**64 - 1, "summary")
        self.assertEqual(result["seed"], 2**64 - 1)

    def test_f35_summary_preserves_business_results_and_random_trajectory(self):
        plan_path = F35 / "execution-plan.json"
        for seed in (0, 1, 7):
            with self.subTest(seed=seed):
                full = self._run_rust(plan_path, seed, "full")
                summary = self._run_rust(plan_path, seed, "summary")
                self.assert_observation_equivalent(full, summary)

    def test_truncated_horizon_preserves_observation_isolation(self):
        plan_path = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
        plan = ExecutionPlan.from_dict(json.loads(plan_path.read_text()))
        expected = SimpyReferenceRuntime(plan, seed=0).run(until=35)
        full = self._run_rust(plan_path, 0, "full", until=35)
        summary = self._run_rust(plan_path, 0, "summary", until=35)
        self.assertIsNone(first_divergence(expected, full))
        self.assertEqual(full["time"], 35)
        self.assertEqual(full["stop_reason"], "requested_until")
        self.assert_observation_equivalent(full, summary)

    def test_unknown_observation_level_fails_explicitly(self):
        plan_path = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
        output = Path(self.tempdir.name) / "invalid-observation.json"
        completed = subprocess.run(
            [
                str(self.binary),
                str(plan_path),
                str(output),
                "--observation-level",
                "silent",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("unsupported observation level", completed.stderr)

    def test_batch_order_is_input_stable_and_thread_count_invariant(self):
        plan_path = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
        seeds = (7, 0, 7, 1)
        by_observation = {}
        for observation_level in ("full", "summary"):
            serial = self._run_rust_batch(
                plan_path, seeds, 1, observation_level, until=35
            )
            parallel = self._run_rust_batch(
                plan_path, seeds, 3, observation_level, until=35
            )
            self.assertEqual(
                [item["sample_index"] for item in parallel["samples"]], list(range(4))
            )
            self.assertEqual(
                [item["seed"] for item in parallel["samples"]], list(seeds)
            )
            self.assertEqual(serial["samples"], parallel["samples"])
            self.assertEqual(serial["worker_threads"], 1)
            self.assertEqual(parallel["worker_threads"], 3)
            by_observation[observation_level] = parallel

        for full, summary in zip(
            by_observation["full"]["samples"],
            by_observation["summary"]["samples"],
            strict=True,
        ):
            self.assertEqual(full["sample_index"], summary["sample_index"])
            self.assertEqual(full["seed"], summary["seed"])
            self.assert_observation_equivalent(full["result"], summary["result"])


if __name__ == "__main__":
    unittest.main()
