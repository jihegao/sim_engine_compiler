"""PRIVATE controls: hand-authored positives and mechanism-removal mutations.

Never give this file or private/oracles.json to generating agents. Controls
validate the harness/oracle, and are not observations of LLM modeling success.
"""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluator import evaluate
from sim_engine_compiler.integrations.spare_mvp.bounded import import_bounded_business
from sim_engine_compiler.domains.aircraft_support.bounded import lower_bounded, operation_contracts
from sim_engine_compiler.compiler.bounded_layout import compile_bounded
from sim_engine_compiler.domains.aircraft_support.bounded_runtime import BoundedAircraftRuntime
from sim_engine_compiler.ir.bounded import BUSINESS, CORE, PLAN, Document

ORACLES = json.loads((Path(__file__).parent / "private/oracles.json").read_text())["tasks"]


def control(task_id):
    return copy.deepcopy(ORACLES[task_id]["internal_control"])


def execute(candidate):
    canonical = {"schema_version": "aircraft-bounded-input/v1",
                 "semantic_profile": "aircraft-bounded-events/v1", "model": candidate["model"]}
    business = import_bounded_business(canonical)
    business = Document.from_dict(business.to_dict(), BUSINESS)
    core = lower_bounded(business)
    core = Document.from_dict(core.to_dict(), CORE)
    plan = compile_bounded(core, operations=operation_contracts())
    plan = Document.from_dict(plan.to_dict(), PLAN)
    return BoundedAircraftRuntime(plan).run()


class EvaluatorTests(unittest.TestCase):
    def assert_rejected(self, candidate, behavior=False):
        result = execute(candidate)
        score = evaluate(candidate, result)
        self.assertFalse(score["accepted"])
        self.assertTrue(any(not c["passed"] and "STRUCT" in c["id"] for c in score["checks"]))
        if behavior:
            self.assertTrue(any(not c["passed"] and "-R" in c["id"] for c in score["checks"]), score)

    def test_six_hand_calculated_positive_controls(self):
        for task_id in ("T01", "T02", "T03", "T04", "T05", "T06"):
            with self.subTest(task_id=task_id):
                candidate = control(task_id)
                score = evaluate(candidate, execute(candidate))
                self.assertTrue(score["accepted"], [c for c in score["checks"] if not c["passed"]])

    def test_missing_runtime_result_never_accepts_model(self):
        self.assertFalse(evaluate(control("T01"))["accepted"])

    def test_resource_capacity_mutation(self):
        candidate = control("T01")
        candidate["model"]["resources"][0]["capacity"] = 1
        self.assert_rejected(candidate, behavior=True)

    def test_minutes_left_unconverted_mutation(self):
        candidate = control("T02")
        candidate["model"]["processes"][0]["scalar_hours"] = 18
        self.assert_rejected(candidate, behavior=True)

    def test_serial_step_omission_mutation(self):
        candidate = control("T03")
        candidate["model"]["processes"][0]["steps"].pop()
        self.assert_rejected(candidate, behavior=True)

    def test_cancellation_cutoff_mutation(self):
        candidate = control("T04")
        candidate["model"]["missions"][0]["delay_hours"] = .3
        self.assert_rejected(candidate, behavior=True)

    def test_dependency_omission_mutation(self):
        candidate = control("T05")
        candidate["model"]["missions"][1]["depends_on"] = []
        self.assert_rejected(candidate, behavior=True)

    def test_pm_omission_mutation(self):
        candidate = control("T06")
        candidate["model"]["aircraft"][0]["pm"] = None
        self.assert_rejected(candidate, behavior=True)

    def test_fault_omission_mutation(self):
        candidate = control("T06")
        candidate["model"]["external_events"] = []
        candidate["model"]["rng_profile"] = "none"
        self.assert_rejected(candidate, behavior=True)

    def test_shrinking_fleet_and_demand_is_rejected(self):
        candidate = control("T01")
        candidate["model"]["aircraft"].pop()
        candidate["model"]["missions"][0]["requirements"]["utility"] = 2
        self.assert_rejected(candidate, behavior=True)

    def test_result_from_another_candidate_cannot_be_reused(self):
        score = evaluate(control("T02"), execute(control("T01")))
        self.assertFalse(score["accepted"])
        self.assertFalse(next(c["passed"] for c in score["checks"] if c["id"] == "execution.input_binding"))

    def test_forged_stale_completion_is_detected(self):
        candidate = control("T04")
        result = execute(candidate)
        result["trace"].append({"kind": "work_finished", "hour": 1.7,
                                "time_ticks": 6_120_000_000, "mission": "tight"})
        self.assertFalse(evaluate(candidate, result)["accepted"])

    def test_equivalent_table_order_can_pass(self):
        candidate = control("T01")
        candidate["model"]["aircraft"].reverse()
        self.assertTrue(evaluate(candidate, execute(candidate))["accepted"])

    def test_explicit_capacity_question_passes(self):
        candidate = dict(task_id="T07", status="clarify", model=None,
                         questions=[dict(field="resources/staff/capacity", question="staff总容量是多少？")],
                         reason="资源容量未提供，无法确定并发准备数量。")
        self.assertTrue(evaluate(candidate)["accepted"])
        candidate["questions"][0]["field"] = "aircraft/count"
        self.assertFalse(evaluate(candidate)["accepted"])

    def test_guessed_capacity_is_rejected_even_if_executable(self):
        candidate = control("T01")
        candidate["task_id"] = "T07"
        self.assertFalse(evaluate(candidate, execute(candidate))["accepted"])

    def test_capability_refusal_passes_and_silent_downgrade_fails(self):
        candidate = dict(task_id="T08", status="unsupported", model=None, questions=[],
                         reason="指定bounded profile不支持内生指数随机故障；它只能接受显式外生fault事件，不能按seed采样。")
        self.assertTrue(evaluate(candidate)["accepted"])
        candidate["reason"] = "不支持"
        self.assertFalse(evaluate(candidate)["accepted"])
        candidate = control("T06")
        candidate["task_id"] = "T08"
        self.assertFalse(evaluate(candidate, execute(candidate))["accepted"])


if __name__ == "__main__":
    unittest.main()
