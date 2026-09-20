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

    def _run_rust(self, plan_path: Path, seed: int) -> dict:
        output = Path(self.tempdir.name) / f"{plan_path.stem}-{seed}.json"
        subprocess.run(
            [str(self.binary), str(plan_path), str(output), "--seed", str(seed)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())

    def _run_rust_batch(
        self, plan_path: Path, seeds: tuple[int, ...], worker_threads: int
    ) -> dict:
        suffix = "-".join(str(seed) for seed in seeds)
        output = Path(self.tempdir.name) / f"{plan_path.stem}-batch-{worker_threads}-{suffix}.json"
        subprocess.run(
            [
                str(self.binary),
                str(plan_path),
                str(output),
                "--seeds",
                ",".join(str(seed) for seed in seeds),
                "--worker-threads",
                str(worker_threads),
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())

    def test_synthetic_slices_match_saved_python_results(self):
        for name in SYNTHETIC:
            with self.subTest(case=name):
                prefix = "b1" if name == "b1" else name
                plan_path = ROOT / "tests" / "fixtures" / "synthetic" / f"{prefix}-execution-plan.json"
                expected_path = ROOT / "tests" / "fixtures" / "synthetic" / f"{prefix}-reference-result.json"
                expected = json.loads(expected_path.read_text())
                actual = self._run_rust(plan_path, 0)
                self.assertIsNone(first_divergence(expected, actual))

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

    def test_batch_order_is_input_stable_and_thread_count_invariant(self):
        plan_path = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
        seeds = (7, 0, 7, 1)
        serial = self._run_rust_batch(plan_path, seeds, 1)
        parallel = self._run_rust_batch(plan_path, seeds, 3)

        self.assertEqual([item["sample_index"] for item in parallel["samples"]], list(range(4)))
        self.assertEqual([item["seed"] for item in parallel["samples"]], list(seeds))
        self.assertEqual(serial["samples"], parallel["samples"])
        self.assertEqual(serial["worker_threads"], 1)
        self.assertEqual(parallel["worker_threads"], 3)


if __name__ == "__main__":
    unittest.main()
