from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from sim_engine_compiler.compiler import CompilationError, compile_aircraft_support

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/synthetic"


class WorkInputValidationTests(unittest.TestCase):
    def failure_input(self, distribution):
        inputs = json.loads((FIXTURES / "b2-failure-repair.json").read_text())
        component = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "radar-lru"
        )
        component["failure_distribution"] = distribution
        return inputs

    def test_shared_python_rust_contract(self):
        base = json.loads((FIXTURES / "b1-daily-operations.json").read_text())
        cases = json.loads((FIXTURES / "work-input-validation.json").read_text())
        for case in cases:
            for profile in ("legacy-minute-v1", "event-time-v2"):
                with self.subTest(case=case["name"], profile=profile):
                    inputs = copy.deepcopy(base)
                    target = inputs
                    path = ""
                    for part in case["path"][:-1]:
                        target = target[part]
                    for part in case["path"]:
                        path += f"[{part}]" if isinstance(part, int) else ("." if path else "") + part
                    target[case["path"][-1]] = case["value"]
                    if "error" in case:
                        with self.assertRaises(CompilationError) as raised:
                            compile_aircraft_support(inputs, semantic_profile=profile)
                        self.assertEqual(raised.exception.code, case["error"])
                        self.assertEqual(raised.exception.source_path, path)
                        self.assertIn(path, str(raised.exception))
                    else:
                        plan = compile_aircraft_support(inputs, semantic_profile=profile)
                        if "expected_minutes" in case:
                            self.assertEqual(plan.activities[0].steps[0].duration_minutes, case["expected_minutes"])
                        if "expected_component" in case:
                            self.assertEqual(plan.activities[0].equipment_component_index, case["expected_component"])

    def test_valid_component_binding_is_preserved(self):
        inputs = json.loads((FIXTURES / "b2-failure-repair.json").read_text())
        component_id = inputs["equipment_tree"]["components"][0]["id"]
        inputs["support_activities"]["activities"][0]["equipment_id"] = component_id
        self.assertEqual(compile_aircraft_support(inputs).activities[0].equipment_component_index, 0)

    def test_explicit_mtbf_uses_aircraft_flight_hour_contract(self):
        inputs = self.failure_input({
            "distributionType": "exponential",
            "mtbf": 50,
            "timeUnit": "hour",
            "timeBasis": "flight_hour",
        })
        for profile in ("legacy-minute-v1", "event-time-v2"):
            with self.subTest(profile=profile):
                plan = compile_aircraft_support(inputs, semantic_profile=profile)
                component = next(item for item in plan.components if item.component_id == "radar-lru")
                self.assertEqual(component.failure_rate_per_hour, 0.02)

    def test_quantity_does_not_scale_single_component_rate(self):
        inputs = self.failure_input({
            "distributionType": "exponential",
            "mtbf": 50,
            "timeUnit": "hour",
            "timeBasis": "flight_hour",
        })
        component_input = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "radar-lru"
        )
        component_input["quantity"] = 3

        for profile in ("legacy-minute-v1", "event-time-v2"):
            with self.subTest(profile=profile):
                plan = compile_aircraft_support(inputs, semantic_profile=profile)
                component = next(item for item in plan.components if item.component_id == "radar-lru")
                self.assertEqual(component.quantity, 3)
                self.assertEqual(component.failure_rate_per_hour, 0.02)
                self.assertEqual(component.failure_threshold, 1)

    def test_fused_compile_accepts_explicit_k_out_of_n_and_rejects_malformed_shape(self):
        inputs = self.failure_input({"distributionType": "exponential", "rate": 0.5})
        for item in inputs["equipment_tree"]["components"]:
            item["component_type_id"] = item["id"]
        component = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "radar-lru"
        )
        component["quantity"] = 3
        component["k_out_of_n"] = {"enabled": True, "k": 2, "n": 3}

        plan = compile_aircraft_support(inputs)
        self.assertEqual(plan.components, ())
        self.assertEqual(plan.reliability_policy, "instance-redundancy/v1")
        group = next(
            item for item in plan.component_groups if item.group_id == "radar-lru"
        )
        self.assertEqual((group.redundancy_kind, group.redundancy_k, group.redundancy_n),
                         ("k_out_of_n", 2, 3))
        self.assertNotIn("failure_threshold", plan.to_dict())

        component["k_out_of_n"] = {"k": 1, "n": 3}
        with self.assertRaises(CompilationError) as raised:
            compile_aircraft_support(inputs)
        self.assertEqual(raised.exception.code, "invalid_k_out_of_n")

    def test_invalid_mtbf_contract_is_rejected(self):
        valid = {
            "distributionType": "exponential",
            "mtbf": 50,
            "timeUnit": "hour",
            "timeBasis": "flight_hour",
        }
        cases = (
            ({**valid, "mtbf": 0}, "invalid_mtbf", ".mtbf"),
            ({**valid, "mtbf": -1}, "invalid_mtbf", ".mtbf"),
            ({key: value for key, value in valid.items() if key != "timeUnit"},
             "missing_failure_time_unit", ".timeUnit"),
            ({**valid, "timeUnit": "day"}, "unsupported_failure_time_unit", ".timeUnit"),
            ({key: value for key, value in valid.items() if key != "timeBasis"},
             "missing_failure_time_basis", ".timeBasis"),
            ({**valid, "timeBasis": "calendar_hour"},
             "unsupported_failure_time_basis", ".timeBasis"),
            ({**valid, "distributionType": "weibull"},
             "unsupported_failure_distribution", ".failure_distribution"),
        )
        for distribution, code, path_suffix in cases:
            for profile in ("legacy-minute-v1", "event-time-v2"):
                with self.subTest(distribution=distribution, profile=profile):
                    with self.assertRaises(CompilationError) as raised:
                        compile_aircraft_support(
                            self.failure_input(distribution), semantic_profile=profile
                        )
                    self.assertEqual(raised.exception.code, code)
                    self.assertTrue(raised.exception.source_path.endswith(path_suffix))

    def test_unknown_legacy_distribution_does_not_become_zero_rate(self):
        inputs = self.failure_input({"distributionType": "gamma", "rate": 0.5})
        with self.assertRaises(CompilationError) as raised:
            compile_aircraft_support(inputs)
        self.assertEqual(raised.exception.code, "unsupported_failure_distribution")

    def test_legacy_rate_input_retains_existing_conversion(self):
        inputs = json.loads((FIXTURES / "b2-failure-repair.json").read_text())
        component = next(
            item for item in compile_aircraft_support(inputs).components
            if item.component_id == "radar-lru"
        )
        self.assertEqual(component.failure_rate_per_hour, 20.0)

    def test_all_five_saved_plans_unchanged(self):
        pairs = [(FIXTURES / f"{source}.json", FIXTURES / f"{plan}.json") for source, plan in (
            ("b1-daily-operations", "b1-execution-plan"),
            ("b2-failure-repair", "b2-failure-repair-execution-plan"),
            ("b2-preventive-maintenance", "b2-preventive-maintenance-execution-plan"),
            ("b3-upstream-transport", "b3-upstream-transport-execution-plan"),
        )]
        f35 = ROOT / "tests/fixtures/spare_mvp/f35-43day-5352a0d"
        pairs.append((f35 / "simulation-inputs.json", f35 / "execution-plan.json"))
        for source, expected in pairs:
            with self.subTest(source=source):
                actual = compile_aircraft_support(json.loads(source.read_text()))
                self.assertEqual(json.loads(json.dumps(actual.to_dict())), json.loads(expected.read_text()))
