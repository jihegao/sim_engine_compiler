from __future__ import annotations

import gzip
import json
from pathlib import Path
import unittest

from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "spare_mvp" / "f35-43day-5352a0d"
SEEDS = (0, 1, 7)
CORE_METRICS = {
    "planned_sorties",
    "planned_mission_waves",
    "successful_mission_waves",
    "mission_success_rate",
    "launched_sorties",
    "completed_sorties",
    "failed_sorties",
    "cancelled_sorties",
    "delayed_sorties",
    "avg_departure_delay",
    "lru_failures",
    "in_flight_failures",
    "preventive_maintenance_events",
    "failed_count",
    "repairing_count",
    "postflight_count",
    "spare_stock_total",
    "spare_consumed_total",
    "spare_demand_total",
    "spare_immediately_filled_total",
    "spare_fill_rate",
    "shortage_events",
    "elapsed_minutes",
    "stop_reason",
}
BUSINESS_KINDS = {
    "mission_launched",
    "component_failed",
    "aircraft_failed",
    "mission_failed_returned",
    "mission_returned_with_component_failure",
    "repair_completed",
    "preventive_created",
    "preventive_completed",
    "spare_request",
    "spare_shortage",
    "spare_consumed",
    "mission_cancelled",
    "mission_success_point_succeeded",
    "mission_success_point_failed",
    "postflight_completed",
    "simulation_stopped",
}


def _oracle(seed: int) -> dict:
    path = FIXTURE / "oracle" / f"f35-oracle-v2-seed-{seed}.json.gz"
    with gzip.open(path, "rt") as handle:
        return json.load(handle)


def _business_timeline(trace: list[dict]) -> list[tuple]:
    return [
        (item["time"], item["phase"], item["kind"], item["entity"])
        for item in trace
        if item["kind"] in BUSINESS_KINDS
    ]


def _sample_projection(samples: list[dict]) -> list[dict]:
    keys = (
        "sequence",
        "time",
        "phase",
        "stream",
        "distribution",
        "component_id",
        "rate_per_hour",
        "value_minutes",
    )
    return [{key: item[key] for key in keys} for item in samples]


class F35ReferenceConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inputs = json.loads((FIXTURE / "simulation-inputs.json").read_text())
        cls.plan = compile_aircraft_support(inputs)
        cls.results = {
            seed: SimpyReferenceRuntime(cls.plan, seed=seed).run() for seed in SEEDS
        }
        cls.oracles = {seed: _oracle(seed) for seed in SEEDS}

    def test_core_metrics_match_for_required_seeds(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                expected = {
                    key: self.oracles[seed]["metrics"][key] for key in CORE_METRICS
                }
                actual = {key: self.results[seed]["metrics"][key] for key in CORE_METRICS}
                self.assertIsNone(first_divergence(expected, actual))

    def test_checked_in_plan_has_fixed_identity(self):
        manifest = json.loads((FIXTURE / "manifest.json").read_text())
        saved = ExecutionPlan.from_dict(
            json.loads((FIXTURE / "execution-plan.json").read_text())
        )
        self.assertEqual(saved, self.plan)
        self.assertEqual(saved.source_inputs_sha256, manifest["inputs_sha256"])
        self.assertEqual(saved.fingerprint, manifest["execution_plan_fingerprint"])

    def test_terminal_state_and_resource_ledgers_match_for_required_seeds(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                self.assertIsNone(
                    first_divergence(
                        self.oracles[seed]["terminal_state"],
                        self.results[seed]["terminal_state"],
                    )
                )

    def test_random_requests_match_for_required_seeds(self):
        # CPython on Linux and macOS can differ by one or two final bits in
        # libm-backed logarithms. Event minutes and every discrete state remain exact.
        for seed in SEEDS:
            with self.subTest(seed=seed):
                self.assertIsNone(
                    first_divergence(
                        _sample_projection(self.oracles[seed]["sample_requests"]),
                        _sample_projection(self.results[seed]["sample_requests"]),
                        float_rel_tol=2e-15,
                        float_abs_tol=1e-12,
                    )
                )

    def test_business_event_time_phase_and_binding_match_for_required_seeds(self):
        for seed in SEEDS:
            with self.subTest(seed=seed):
                self.assertIsNone(
                    first_divergence(
                        _business_timeline(self.oracles[seed]["trace"]),
                        _business_timeline(self.results[seed]["trace"]),
                    )
                )


if __name__ == "__main__":
    unittest.main()
