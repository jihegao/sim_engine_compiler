from __future__ import annotations

import json
from pathlib import Path
import unittest

import sim_engine_compiler
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
EXPECTED = ROOT / "tests" / "fixtures" / "synthetic" / "b1-reference-result.json"
NON_TRACE_RESULT_FIELDS = (
    "plan_fingerprint",
    "seed",
    "time",
    "stop_reason",
    "sample_requests",
    "metrics",
    "terminal_state",
)


class PythonBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not sim_engine_compiler.native_available():
            raise AssertionError(
                "Rust binding is required; rebuild it with "
                "`uv pip install --python .venv/bin/python -e .`"
            )

    def assert_observation_equivalent(self, full: dict, summary: dict):
        self.assertEqual(summary["trace"], [])
        for field in NON_TRACE_RESULT_FIELDS:
            self.assertEqual(summary[field], full[field], field)

    def test_single_sample_matches_saved_reference(self):
        expected = json.loads(EXPECTED.read_text())
        actual = sim_engine_compiler.run_plan(PLAN, seed=0)
        self.assertIsNone(first_divergence(expected, actual))

    def test_summary_omits_trace_without_changing_business_or_rng_results(self):
        for until in (None, 35):
            with self.subTest(until=until):
                full = sim_engine_compiler.run_plan(
                    PLAN, seed=0, until=until, observation_level="full"
                )
                summary = sim_engine_compiler.run_plan(
                    PLAN, seed=0, until=until, observation_level="summary"
                )
                self.assert_observation_equivalent(full, summary)
        self.assertEqual(full["time"], 35)
        self.assertEqual(full["stop_reason"], "requested_until")

    def test_parallel_batch_preserves_input_order_and_duplicate_seeds(self):
        seeds = (7, 0, 7, 1)
        by_observation = {}
        for observation_level in ("full", "summary"):
            serial = sim_engine_compiler.run_batch(
                PLAN,
                seeds,
                worker_threads=1,
                until=35,
                observation_level=observation_level,
            )
            parallel = sim_engine_compiler.run_batch(
                PLAN,
                seeds,
                worker_threads=3,
                until=35,
                observation_level=observation_level,
            )
            self.assertEqual(
                [sample["sample_index"] for sample in parallel["samples"]],
                list(range(len(seeds))),
            )
            self.assertEqual(
                [sample["seed"] for sample in parallel["samples"]], list(seeds)
            )
            self.assertEqual(serial["samples"], parallel["samples"])
            by_observation[observation_level] = parallel

        for full, summary in zip(
            by_observation["full"]["samples"],
            by_observation["summary"]["samples"],
            strict=True,
        ):
            self.assertEqual(full["sample_index"], summary["sample_index"])
            self.assertEqual(full["seed"], summary["seed"])
            self.assert_observation_equivalent(full["result"], summary["result"])

    def test_invalid_batch_requests_fail_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "at least one seed"):
            sim_engine_compiler.run_batch(PLAN, [], worker_threads=1)
        with self.assertRaisesRegex(RuntimeError, "greater than zero"):
            sim_engine_compiler.run_batch(PLAN, [0], worker_threads=0)


if __name__ == "__main__":
    unittest.main()
