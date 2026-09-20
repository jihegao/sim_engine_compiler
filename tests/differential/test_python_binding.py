from __future__ import annotations

import json
from pathlib import Path
import unittest

import sim_engine_compiler
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
EXPECTED = ROOT / "tests" / "fixtures" / "synthetic" / "b1-reference-result.json"


@unittest.skipUnless(
    sim_engine_compiler.native_available(),
    "install the project with maturin to exercise the Rust Python binding",
)
class PythonBindingTests(unittest.TestCase):
    def test_single_sample_matches_saved_reference(self):
        expected = json.loads(EXPECTED.read_text())
        actual = sim_engine_compiler.run_plan(PLAN, seed=0)
        self.assertIsNone(first_divergence(expected, actual))

    def test_parallel_batch_preserves_input_order_and_duplicate_seeds(self):
        seeds = (7, 0, 7, 1)
        serial = sim_engine_compiler.run_batch(PLAN, seeds, worker_threads=1)
        parallel = sim_engine_compiler.run_batch(PLAN, seeds, worker_threads=3)
        self.assertEqual(
            [sample["sample_index"] for sample in parallel["samples"]],
            list(range(len(seeds))),
        )
        self.assertEqual(
            [sample["seed"] for sample in parallel["samples"]], list(seeds)
        )
        self.assertEqual(serial["samples"], parallel["samples"])

    def test_invalid_batch_requests_fail_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "at least one seed"):
            sim_engine_compiler.run_batch(PLAN, [], worker_threads=1)
        with self.assertRaisesRegex(RuntimeError, "greater than zero"):
            sim_engine_compiler.run_batch(PLAN, [0], worker_threads=0)


if __name__ == "__main__":
    unittest.main()
