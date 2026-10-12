"""PRIVATE controls; never exposed to participant agents.

Expected behavior is manually derived in private/cases.json. Tests execute those
controls but do not regenerate expected observations from the runtime.
"""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from experiments.codex_modeling_pilot.runner import run_candidate
from experiments.codex_modeling_round2.controller import evaluate_candidate, load_cases
from experiments.codex_modeling_round2.evaluator import apply_changes, evaluate, normalized_work


def model_candidate(case):
    return {"task_id": case["task_id"], "status": "model", "model": copy.deepcopy(case["reference_model"]),
            "questions": [], "reason": "Private hand-authored control; not an LLM submission."}


class RoundTwoControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        book = load_cases()
        cls.cases = book["development"] + book["holdout"]
        cls.models = [c for c in cls.cases if c["category"] in ("modeling", "composition")]

    def fresh_run(self, candidate):
        with tempfile.TemporaryDirectory(prefix="round2-private-control-") as parent:
            return run_candidate(candidate, Path(parent) / "run", score=False)

    def test_all_reference_controls_and_hidden_interventions(self):
        for case in self.models:
            with self.subTest(task_id=case["task_id"]):
                with tempfile.TemporaryDirectory(prefix="round2-private-positive-") as parent:
                    report = evaluate_candidate(model_candidate(case), Path(parent) / "control", case)
                    self.assertTrue(report["accepted"], {
                        "baseline": [c for c in report["checks"] if not c["passed"]],
                        "interventions": [{"id": i["id"], "error": i.get("error"),
                            "checks": [c for c in i.get("assessment", {}).get("checks", []) if not c["passed"]]}
                            for i in report["interventions"] if not i["accepted"]],
                        "error": report["error"]})

    def test_every_model_has_discriminating_mutation(self):
        for case in self.models:
            self.assertTrue(case.get("mutations"), case["task_id"])
            for mutation in case["mutations"]:
                with self.subTest(task_id=case["task_id"], mutation=mutation["id"]):
                    candidate = model_candidate(case)
                    candidate["model"] = apply_changes(candidate["model"], mutation["changes"])
                    run = self.fresh_run(candidate)
                    score = evaluate(candidate, run["result"], case)
                    self.assertFalse(score["accepted"], "mutation escaped assessment")
                    if run["executed"] and mutation.get("expected_failed_ids"):
                        failures = {c["id"] for c in score["checks"] if not c["passed"]}
                        self.assertTrue(failures.intersection(mutation["expected_failed_ids"]), failures)

    def test_results_cannot_cross_candidates(self):
        first, second = self.models[:2]
        result = self.fresh_run(model_candidate(first))["result"]
        score = evaluate(model_candidate(second), result, second)
        self.assertFalse(score["accepted"])
        self.assertFalse(next(c["passed"] for c in score["checks"] if c["id"] == "execution.input_binding"))

    def test_malformed_envelopes_reject(self):
        case = self.models[0]
        good = model_candidate(case)
        bad_values = [None, [], {}, dict(good, unexpected=True), dict(good, status="probably"),
                      dict(good, questions=[{"field": "x", "question": "missing?"}]),
                      dict(good, model=None), dict(good, reason=[])]
        for candidate in bad_values:
            with self.subTest(candidate=repr(candidate)[:60]):
                self.assertFalse(evaluate(candidate, None, case)["accepted"])

    def test_missing_runtime_never_accepts_model(self):
        case = self.models[0]
        self.assertFalse(evaluate(model_candidate(case), None, case)["accepted"])

    def test_unrelated_table_order_is_accepted(self):
        for case in self.models:
            with self.subTest(task_id=case["task_id"]):
                candidate = model_candidate(case)
                for table in ("resources", "processes", "nodes", "routes"):
                    candidate["model"][table].reverse()
                run = self.fresh_run(candidate)
                score = evaluate(candidate, run["result"], case)
                self.assertTrue(score["accepted"], [c for c in score["checks"] if not c["passed"]])

    def test_equivalent_resource_free_work_is_accepted(self):
        tested = 0
        for case in self.models:
            candidate = model_candidate(case)
            changed = False
            for process in candidate["model"]["processes"]:
                steps = process["steps"] or [{"duration_hours": process["scalar_hours"], "demands": {}}]
                if len(steps) == 1 and not steps[0]["demands"] and steps[0]["duration_hours"] > 0:
                    duration = steps[0]["duration_hours"]
                    process["steps"] = [{"id": "equivalent-first", "duration_hours": duration / 2, "demands": {}},
                                        {"id": "equivalent-second", "duration_hours": duration / 2, "demands": {}}]
                    changed = True
                    break
            if changed:
                run = self.fresh_run(candidate)
                score = evaluate(candidate, run["result"], case)
                self.assertTrue(score["accepted"], {"task": case["task_id"], "failures": [c for c in score["checks"] if not c["passed"]]})
                tested += 1
        self.assertGreater(tested, 0, "requires at least one meaningful equivalent-expression control")

    def test_resource_boundaries_are_not_collapsed(self):
        divided = [{"duration_hours": .1, "demands": {"crew": 1}}, {"duration_hours": .2, "demands": {"crew": 1}}]
        self.assertEqual(len(normalized_work(divided)), 2)
        instant = [{"duration_hours": 0, "demands": {"crew": 1}}]
        self.assertEqual(normalized_work(instant), instant)

    def test_forged_resource_release_fails_independent_ledger(self):
        case = next(c for c in self.models if c["reference_model"]["resources"])
        candidate = model_candidate(case)
        result = self.fresh_run(candidate)["result"]
        resource = candidate["model"]["resources"][0]["id"]
        result["trace"].append({"sequence": len(result["trace"]), "time_ticks": 0, "hour": 0,
                                "kind": "resource_released", "owner": "forged", "resource": resource, "quantity": 1})
        score = evaluate(candidate, result, case)
        self.assertFalse(next(c["passed"] for c in score["checks"] if c["id"] == "ledger.independent"))

    def test_clarification_and_refusal_are_only_automatic_screens(self):
        for case in self.cases:
            if case["category"] not in ("clarify", "unsupported"):
                continue
            with self.subTest(task_id=case["task_id"]):
                if case["category"] == "clarify":
                    questions = [{"field": q.get("field_aliases", [q["concept"]])[0],
                                  "question": "Please clarify " + " ".join(group[0] for group in q["keyword_groups"])}
                                 for q in case["clarification"]["questions"]]
                    reason = "A required business condition is missing."
                else:
                    questions = []
                    reason = "Unsupported: " + " ".join(group[0] for group in case["unsupported"]["keyword_groups"])
                candidate = {"task_id": case["task_id"], "status": case["category"], "model": None,
                             "questions": questions, "reason": reason}
                score = evaluate(candidate, None, case)
                self.assertTrue(score["accepted"], score)
                self.assertEqual(score["assessment_kind"], "automatic_concept_screen")
                self.assertTrue(score["semantic_review_required"])
                candidate["questions"] = [{"field": "unrelated", "question": "Weather?"}] if questions else []
                candidate["reason"] = "Unknown."
                self.assertFalse(evaluate(candidate, None, case)["accepted"])

    def test_preregistered_answered_controls(self):
        for case in self.cases:
            if case["category"] != "clarify":
                continue
            answered = case["clarification"]["answered_case"]
            self.assertEqual(answered["task_id"], case["task_id"])
            with self.subTest(task_id=case["task_id"]):
                with tempfile.TemporaryDirectory(prefix="round2-private-followup-") as parent:
                    report = evaluate_candidate(model_candidate(answered), Path(parent) / "control", answered)
                    self.assertTrue(report["accepted"], [c for c in report["checks"] if not c["passed"]])
                for mutation in answered.get("mutations", []):
                    candidate = model_candidate(answered)
                    candidate["model"] = apply_changes(candidate["model"], mutation["changes"])
                    run = self.fresh_run(candidate)
                    score = evaluate(candidate, run["result"], answered)
                    self.assertFalse(score["accepted"], "answered-model mutation escaped assessment")

    def test_public_execution_never_imports_evaluator(self):
        candidate = model_candidate(self.models[0])
        with patch("experiments.codex_modeling_pilot.runner.importlib.import_module", side_effect=AssertionError("oracle access forbidden")):
            run = self.fresh_run(candidate)
            self.assertTrue(run["executed"])

    def test_outputs_cannot_overwrite_existing_evidence(self):
        candidate = model_candidate(self.models[0])
        with tempfile.TemporaryDirectory(prefix="round2-private-no-overwrite-") as parent:
            path = Path(parent) / "run"
            run_candidate(candidate, path, score=False)
            with self.assertRaisesRegex(ValueError, "empty"):
                run_candidate(candidate, path, score=False)


if __name__ == "__main__":
    unittest.main()
