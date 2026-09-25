from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from sim_engine_compiler.compiler import CompilationError, compile_aircraft_support

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/synthetic"


class WorkInputValidationTests(unittest.TestCase):
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
