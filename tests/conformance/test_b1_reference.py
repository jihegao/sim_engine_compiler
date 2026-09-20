from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]


class IndependentRuntimeBoundaryTests(unittest.TestCase):
    def test_reference_runtime_has_no_legacy_model_import_or_symbol(self):
        reference_root = ROOT / "src" / "sim_engine_compiler"
        forbidden = ("AircraftSupportV1Model", "spare_mvp_abm")
        for path in reference_root.rglob("*.py"):
            source = path.read_text()
            ast.parse(source, filename=str(path))
            for token in forbidden:
                self.assertNotIn(token, source, f"{path} contains forbidden dependency {token}")


class B1DailyOperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(
            (ROOT / "tests" / "fixtures" / "synthetic" / "b1-daily-operations.json").read_text()
        )
        cls.plan = compile_aircraft_support(cls.inputs)
        cls.result = SimpyReferenceRuntime(cls.plan, seed=0).run()
        cls.oracle = json.loads(
            (ROOT / "tests" / "fixtures" / "synthetic" / "b1-daily-operations-oracle.json").read_text()
        )

    def test_compiles_explicit_plan_without_unsupported_features(self):
        self.assertEqual(self.plan.unsupported_features, ())
        self.assertEqual(len(self.plan.aircraft), 2)
        self.assertEqual(len(self.plan.missions), 2)
        self.assertEqual([mission.planned_start for mission in self.plan.missions], [20, 40])
        self.assertEqual([activity.phase for activity in self.plan.activities], ["preflight", "relaunch", "postflight"])
        self.assertEqual(len(self.plan.fingerprint), 64)
        restored = ExecutionPlan.from_dict(self.plan.to_dict())
        self.assertEqual(restored, self.plan)
        self.assertEqual(restored.fingerprint, self.plan.fingerprint)

    def test_executes_hand_calculable_daily_operations_timeline(self):
        selected = [
            (item["time"], item["phase"], item["kind"], item["entity"])
            for item in self.result["trace"]
            if item["kind"]
            in {
                "mission_launched",
                "mission_returned",
                "mission_success_point_succeeded",
                "postflight_completed",
            }
        ]
        self.assertEqual(
            selected,
            [
                (20, "mission_dispatch", "mission_launched", "sortie-a-d1-w1"),
                (28, "mission_success", "mission_success_point_succeeded", "sortie-a-d1-w1"),
                (30, "mission_returns", "mission_returned", "F35-01"),
                (40, "mission_dispatch", "mission_launched", "sortie-b-d1-w1"),
                (48, "mission_success", "mission_success_point_succeeded", "sortie-b-d1-w1"),
                (50, "mission_returns", "mission_returned", "F35-01"),
                (52, "job_progress_and_completions", "postflight_completed", "F35-01"),
            ],
        )

    def test_relaunch_is_zero_duration_and_postflight_balances_resources(self):
        relaunch = [
            item
            for item in self.result["trace"]
            if item["kind"] == "operations_phase_created"
            and item["details"].get("operations_phase") == "relaunch"
        ]
        self.assertEqual([(item["time"], item["phase"]) for item in relaunch], [(30, "preflight_generation")])
        resources = self.result["terminal_state"]["resources"]
        self.assertEqual(
            resources,
            [{
                "node_id": "flight-line",
                "personnel_in_use": 0,
                "equipment_in_use": 0,
                "inventory": {},
            }],
        )
        aircraft = self.result["terminal_state"]["aircraft"]
        self.assertEqual(aircraft[0]["daily_takeoffs"], 2)
        self.assertFalse(aircraft[0]["postflight_required"])
        self.assertEqual(aircraft[0]["state"], "available")

    def test_core_metrics_are_hand_calculable(self):
        metrics = self.result["metrics"]
        self.assertEqual(metrics["planned_sorties"], 2)
        self.assertEqual(metrics["launched_sorties"], 2)
        self.assertEqual(metrics["completed_sorties"], 2)
        self.assertEqual(metrics["successful_mission_waves"], 2)
        self.assertEqual(metrics["cancelled_sorties"], 0)
        self.assertEqual(metrics["postflight_count"], 0)
        self.assertEqual(metrics["elapsed_minutes"], 60)

    def test_first_divergence_reports_exact_path(self):
        expected = {"trace": [{"time": 20, "rule_id": None}]}
        actual = {"trace": [{"time": 21, "rule_id": "mission.dispatch"}]}
        difference = first_divergence(expected, actual)
        self.assertIsNotNone(difference)
        self.assertEqual(difference.path, "root.trace[0].time")
        self.assertEqual(difference.business_rule_id, "mission.dispatch")

    def test_terminal_state_and_core_metrics_match_independent_legacy_oracle(self):
        self.assertIsNone(
            first_divergence(self.oracle["terminal_state"], self.result["terminal_state"])
        )
        keys = {
            "planned_sorties",
            "planned_mission_waves",
            "successful_mission_waves",
            "mission_success_rate",
            "launched_sorties",
            "completed_sorties",
            "cancelled_sorties",
            "delayed_sorties",
            "postflight_count",
            "avg_departure_delay",
            "elapsed_minutes",
            "stop_reason",
        }
        expected = {key: self.oracle["metrics"][key] for key in keys}
        actual = {key: self.result["metrics"][key] for key in keys}
        self.assertIsNone(first_divergence(expected, actual))

    def test_business_event_time_and_phase_match_legacy_oracle(self):
        business_kinds = {
            "operations_phase_created",
            "operations_step_started",
            "operations_step_completed",
            "operations_phase_completed",
            "preflight_created",
            "preflight_completed",
            "mission_launched",
            "mission_success_point_succeeded",
            "mission_success_point_failed",
            "mission_returned",
            "mission_cancelled",
            "postflight_completed",
            "simulation_stopped",
        }

        def timeline(trace):
            return [
                (item["time"], item["phase"], item["kind"], item["entity"])
                for item in trace
                if item["kind"] in business_kinds
            ]

        self.assertIsNone(
            first_divergence(timeline(self.oracle["trace"]), timeline(self.result["trace"]))
        )


class F35PlanBoundaryTests(unittest.TestCase):
    def test_f35_canonical_input_compiles_to_supported_plan(self):
        inputs = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "spare_mvp"
                / "f35-43day-5352a0d"
                / "simulation-inputs.json"
            ).read_text()
        )
        plan = compile_aircraft_support(inputs)
        manifest = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "spare_mvp"
                / "f35-43day-5352a0d"
                / "manifest.json"
            ).read_text()
        )
        self.assertEqual(len(plan.aircraft), 9)
        self.assertEqual(len(plan.missions), 104)
        self.assertEqual(plan.duration_minutes, 61920)
        self.assertEqual(plan.source_inputs_sha256, manifest["inputs_sha256"])
        self.assertEqual(plan.unsupported_features, ())
        runtime = SimpyReferenceRuntime(plan)
        self.assertEqual(len(runtime.sample_requests), 9 * 423)


class B2FailureRepairTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads(
            (ROOT / "tests" / "fixtures" / "synthetic" / "b2-failure-repair.json").read_text()
        )
        cls.plan = compile_aircraft_support(cls.inputs)
        cls.result = SimpyReferenceRuntime(cls.plan, seed=0).run()
        cls.oracle = json.loads(
            (
                ROOT
                / "tests"
                / "fixtures"
                / "synthetic"
                / "b2-failure-repair-oracle.json"
            ).read_text()
        )

    def test_random_sample_order_and_values_match_oracle(self):
        keys = {
            "sequence",
            "time",
            "phase",
            "stream",
            "distribution",
            "component_id",
            "rate_per_hour",
            "value_minutes",
        }
        expected = [{key: item[key] for key in keys} for item in self.oracle["sample_requests"]]
        actual = [{key: item[key] for key in keys} for item in self.result["sample_requests"]]
        self.assertIsNone(first_divergence(expected, actual))

    def test_failure_repair_timeline_matches_oracle(self):
        kinds = {
            "mission_launched",
            "component_failed",
            "aircraft_failed",
            "maintenance_method_selected",
            "mission_failed_returned",
            "repair_completed",
            "mission_success_point_failed",
            "postflight_completed",
            "simulation_stopped",
        }

        def timeline(trace):
            return [
                (item["time"], item["phase"], item["kind"], item["entity"])
                for item in trace
                if item["kind"] in kinds
            ]

        self.assertIsNone(
            first_divergence(timeline(self.oracle["trace"]), timeline(self.result["trace"]))
        )

    def test_terminal_state_and_failure_metrics_match_oracle(self):
        self.assertIsNone(
            first_divergence(self.oracle["terminal_state"], self.result["terminal_state"])
        )
        keys = {
            "planned_sorties",
            "planned_mission_waves",
            "successful_mission_waves",
            "mission_success_rate",
            "launched_sorties",
            "completed_sorties",
            "failed_sorties",
            "cancelled_sorties",
            "delayed_sorties",
            "lru_failures",
            "in_flight_failures",
            "failed_count",
            "repairing_count",
            "postflight_count",
            "elapsed_minutes",
            "stop_reason",
        }
        expected = {key: self.oracle["metrics"][key] for key in keys}
        actual = {key: self.result["metrics"][key] for key in keys}
        self.assertIsNone(first_divergence(expected, actual))


if __name__ == "__main__":
    unittest.main()
