from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import sim_engine_compiler
from sim_engine_compiler.compiler.aircraft_support import compile_aircraft_support
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT / "tests" / "fixtures" / "synthetic" / "b1-execution-plan.json"
EXPECTED = ROOT / "tests" / "fixtures" / "synthetic" / "b1-reference-result.json"
CANONICAL_INPUTS = (
    ROOT / "tests" / "fixtures" / "synthetic" / "b1-daily-operations.json"
)
F35_CANONICAL_INPUTS = (
    ROOT
    / "tests"
    / "fixtures"
    / "spare_mvp"
    / "f35-43day-5352a0d"
    / "simulation-inputs.json"
)
F35_SWEEP_ORACLE = F35_CANONICAL_INPUTS.with_name("sweep-core-oracle.json")
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

    def test_canonical_batch_exposes_core_envelope_and_cache_identity(self):
        canonical_inputs = json.loads(CANONICAL_INPUTS.read_text())
        requests = [
            {
                "sample_index": 8,
                "seed": 7,
                "sweep": {"failureRate": 1.5},
                "steps": [{"kind": "upstream-metadata-only"}],
                "canonical_inputs": canonical_inputs,
            },
            {
                "sample_index": 3,
                "seed": 0,
                "sweep": {"failureRate": 1.0},
                "canonical_inputs": canonical_inputs,
            },
        ]
        with tempfile.TemporaryDirectory() as cache_dir:
            first = sim_engine_compiler.run_canonical_batch(
                requests, worker_threads=2, cache_dir=cache_dir
            )
            second = sim_engine_compiler.run_canonical_batch(
                requests, worker_threads=1, cache_dir=cache_dir
            )

        self.assertEqual(first["plan_cache_status"], "miss")
        self.assertEqual(second["plan_cache_status"], "hit")
        self.assertEqual(first["worker_count"], 2)
        self.assertEqual(second["worker_count"], 1)
        self.assertEqual(first["engine_metadata"]["semantic_profile"], "event-time-v2")
        self.assertEqual(first["engine_metadata"]["observation_level"], "summary")
        self.assertEqual(
            [sample["sample_index"] for sample in first["samples"]], [3, 8]
        )
        self.assertEqual(first["failed_samples"], [])
        for sample in first["samples"]:
            self.assertEqual(sample["metrics"], sample["result"]["metrics"])
            self.assertEqual(sample["result"]["trace"], [])
            self.assertIn("sample_requests", sample["result"])
            self.assertIn("terminal_state", sample["result"])
            self.assertIn("time", sample["result"])
            self.assertIn("stop_reason", sample["result"])

    def test_canonical_batch_rejects_duplicate_indexes(self):
        canonical_inputs = json.loads(CANONICAL_INPUTS.read_text())
        duplicated = {
            "sample_index": 1,
            "seed": 0,
            "sweep": {},
            "canonical_inputs": canonical_inputs,
        }
        with self.assertRaisesRegex(RuntimeError, "duplicate sample_index 1"):
            sim_engine_compiler.run_canonical_batch([duplicated, duplicated])

    def test_canonical_batch_f35_seeds_match_event_time_plan(self):
        canonical_inputs = json.loads(F35_CANONICAL_INPUTS.read_text())
        seeds = (0, 1, 7)
        plan = compile_aircraft_support(
            canonical_inputs, semantic_profile="event-time-v2"
        )
        expected = [
            sim_engine_compiler.run_plan(
                plan, seed=seed, observation_level="summary"
            )
            for seed in seeds
        ]
        actual = sim_engine_compiler.run_canonical_batch(
            [
                {
                    "sample_index": index,
                    "seed": seed,
                    "sweep": {},
                    "canonical_inputs": canonical_inputs,
                }
                for index, seed in enumerate(seeds)
            ],
            worker_threads=3,
        )
        self.assertEqual(actual["failed_samples"], [])
        self.assertEqual(
            [sample["result"] for sample in actual["samples"]], expected
        )

    def test_canonical_batch_f35_sweeps_match_spare_mvp_core_oracle(self):
        base_inputs = json.loads(F35_CANONICAL_INPUTS.read_text())
        oracle = json.loads(F35_SWEEP_ORACLE.read_text())

        def transformed(sweep: dict) -> dict:
            inputs = copy.deepcopy(base_inputs)
            if "failure_multiplier" in sweep or "failure_rate" in sweep:
                multiplier = sweep.get("failure_multiplier", sweep.get("failure_rate"))
                for component in inputs["equipment_tree"]["components"]:
                    component["failure_rate"] = (
                        float(component.get("failure_rate") or 0) * multiplier
                    )
                    component.setdefault("failure_distribution", {})[
                        "_rate_multiplier"
                    ] = multiplier
            if "spare_multiplier" in sweep:
                multiplier = sweep["spare_multiplier"]
                for node in inputs["support_network"]["nodes"]:
                    for product_id, quantity in node["inventory"].items():
                        node["inventory"][product_id] = round(quantity * multiplier)
            if "support_capacity" in sweep:
                capacity = max(1, int(sweep["support_capacity"]))
                for node in inputs["support_network"]["nodes"]:
                    node["personnel_capacity"] = capacity
                    node["equipment_capacity"] = capacity
            return inputs

        scenarios = list(oracle["scenarios"].items())
        actual = sim_engine_compiler.run_canonical_batch(
            [
                {
                    "sample_index": len(scenarios) - index - 1,
                    "seed": scenario.get("seed", oracle["seed"]),
                    "sweep": scenario["sweep"],
                    "canonical_inputs": transformed(scenario["sweep"]),
                }
                for index, (_name, scenario) in enumerate(scenarios)
            ],
            worker_threads=4,
        )

        self.assertEqual(actual["failed_samples"], [])
        self.assertEqual(
            [sample["sample_index"] for sample in actual["samples"]],
            list(range(len(scenarios))),
        )
        expected_by_sweep = {
            json.dumps(scenario["sweep"], sort_keys=True): scenario
            for scenario in oracle["scenarios"].values()
        }
        for sample in actual["samples"]:
            expected = expected_by_sweep[
                json.dumps(sample["sweep"], sort_keys=True)
            ]
            self.assertEqual(sample["metrics"], expected["metrics"])
            if "time" in expected:
                self.assertEqual(sample["result"]["time"], expected["time"])
            if "stop_reason" in expected:
                self.assertEqual(
                    sample["result"]["stop_reason"], expected["stop_reason"]
                )
            if "terminal_state_jobs_sha256" in expected:
                jobs = sample["result"]["terminal_state"]["jobs"]
                encoded = json.dumps(
                    jobs,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                self.assertEqual(len(jobs), expected["terminal_state_jobs_count"])
                self.assertEqual(
                    hashlib.sha256(encoded).hexdigest(),
                    expected["terminal_state_jobs_sha256"],
                )


if __name__ == "__main__":
    unittest.main()
