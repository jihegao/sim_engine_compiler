from __future__ import annotations

import copy
import unittest

from sim_engine_compiler import compile_model, run_abm_plan
from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.ir import AbmTickPlan
from sim_engine_compiler.reference import AbmRuntimeError
from tests.fixtures.abm_source_semantics.cases import (
    SOURCE_SCHEMA,
    cases,
    setup_lifecycle_case,
)

COORDINATE_TOLERANCE = 1e-12


def _agent_map(result: dict) -> dict[str, dict]:
    return {item["id"]: item for item in result["state"]["agents"]}


def _attempt_projection(result: dict) -> list[dict]:
    projected = []
    for event in result["events"]:
        if event["kind"] != "move_attempt":
            continue
        details = event["details"]
        projected.append(
            {
                "entity": event["entity"],
                "ordinal": details["ordinal"],
                "patch": details["patch"],
                "accepted": details["accepted"],
            }
        )
    return projected


def projection_violations(result: dict, expected: dict) -> list[str]:
    """Return source-oracle projection differences without relaxing discrete fields."""
    violations: list[str] = []
    if "ticks" in expected and result.get("ticks") != expected["ticks"]:
        violations.append("ticks")
    if "stop_reason" in expected and result.get("stop_reason") != expected["stop_reason"]:
        violations.append("stop_reason")
    if "movers" in expected:
        movers = [item["entity"] for item in result["events"] if item["kind"] == "moved"]
        if movers != expected["movers"]:
            violations.append("movers")
    if "traversal_members" in expected:
        members = [
            item["entity_id"]
            for item in result["random_requests"]
            if item["distribution"] == "traversal_key"
        ]
        if members != expected["traversal_members"]:
            violations.append("traversal_members")
    if "attempts" in expected and _attempt_projection(result) != expected["attempts"]:
        violations.append("attempts")
    agents = _agent_map(result)
    for identity, coordinate in expected.get("positions", {}).items():
        actual = [agents[identity]["x"], agents[identity]["y"]]
        if any(abs(left - right) > COORDINATE_TOLERANCE for left, right in zip(actual, coordinate, strict=True)):
            violations.append(f"position:{identity}")
    for identity, heading in expected.get("headings", {}).items():
        if agents[identity]["vars"]["heading"] != heading:
            violations.append(f"heading:{identity}")
    for identity, happy in expected.get("happy", {}).items():
        if agents[identity]["vars"]["happy"] is not happy:
            violations.append(f"happy:{identity}")
    for metric, value in expected.get("metrics", {}).items():
        actual = result["metrics"].get(metric)
        if type(value) is float:
            if type(actual) not in (int, float) or abs(actual - value) > 1e-12:
                violations.append(f"metric:{metric}")
        elif actual != value:
            violations.append(f"metric:{metric}")
    return violations


def _error_code(error: BaseException) -> str | None:
    return getattr(error, "code", None)


class SchellingSourceHandCaseTests(unittest.TestCase):
    def test_nine_exported_cases_have_unique_obligations_and_compile(self):
        fixtures = cases()

        self.assertEqual(len(fixtures), 9)
        self.assertEqual({item["obligation"] for item in fixtures}, set(range(1, 10)))
        self.assertEqual(len({item["case_id"] for item in fixtures}), 9)
        for case in fixtures:
            with self.subTest(case=case["case_id"]):
                plan = compile_model(case["model"]).plan
                self.assertEqual(plan.payload["source_semantics"]["schema_version"], SOURCE_SCHEMA)
                self.assertEqual(plan.payload["source_semantics"]["stop_timing"], "before_tick")

    def test_eight_success_cases_match_frozen_source_projections(self):
        for case in cases():
            if "expected_error" in case:
                continue
            with self.subTest(case=case["case_id"]):
                plan = compile_model(case["model"]).plan
                result = run_abm_plan(plan, random_tape=case["random_tape"])
                self.assertEqual(projection_violations(result, case["projection_expectations"]), [])

    def test_pre_step_stop_draws_nothing_and_completes_no_tick(self):
        case = cases()[0]

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])

        self.assertEqual(result["random_requests"], [])
        self.assertFalse(any(event["kind"] == "moved" for event in result["events"]))
        self.assertEqual(result["ticks"], 0)

    def test_selector_freezes_membership_before_random_order(self):
        case = next(item for item in cases() if item["case_id"] == "frozen-membership")

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])

        traversal = [item["entity_id"] for item in result["random_requests"] if item["distribution"] == "traversal_key"]
        self.assertEqual(traversal, ["A", "B"])
        self.assertEqual([item["entity"] for item in result["events"] if item["kind"] == "moved"], ["A", "B"])
        self.assertFalse(_agent_map(result)["C"]["vars"]["happy"])

        # Immediately after A moves, but before scheduled B moves, B changes
        # from 1/3 to 2/4 similar while C changes from 1/2 to 1/3.  Selection
        # nevertheless remains the tick-start set {A, B}.
        initial = {
            item["id"]: (round(item["x"]), round(item["y"]), item["vars"]["group"])
            for item in case["model"]["initial_state"]["agents"]
        }
        after_a = dict(initial)
        after_a["A"] = (1, 2, "blue")

        def ratio(identity, state):
            x, y, group = state[identity]
            neighbors = []
            for other, (ox, oy, other_group) in state.items():
                if other == identity:
                    continue
                dx, dy = abs(x - ox), abs(y - oy)
                dx, dy = min(dx, 5 - dx), min(dy, 5 - dy)
                if max(dx, dy) == 1:
                    neighbors.append(other_group)
            return sum(value == group for value in neighbors), len(neighbors)

        self.assertEqual(ratio("B", initial), (1, 3))
        self.assertEqual(ratio("B", after_a), (2, 4))
        self.assertEqual(ratio("C", initial), (1, 2))
        self.assertEqual(ratio("C", after_a), (1, 3))

    def test_rejected_attempt_starts_next_attempt_from_mutated_state(self):
        case = next(item for item in cases() if item["case_id"] == "rejected-attempt-carries-state")

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
        attempts = [item["details"] for item in result["events"] if item["kind"] == "move_attempt"]

        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0]["from"], [0.0, 0.0])
        self.assertAlmostEqual(attempts[0]["trial_position"][0], 1.0, delta=COORDINATE_TOLERANCE)
        self.assertAlmostEqual(attempts[0]["trial_position"][1], 0.0, delta=COORDINATE_TOLERANCE)
        self.assertEqual(attempts[0]["heading_before"], 0.0)
        self.assertEqual(attempts[0]["heading_after"], 90.0)
        self.assertEqual(attempts[1]["from"], attempts[0]["trial_position"])
        self.assertEqual(attempts[1]["heading_before"], 90.0)
        self.assertEqual(attempts[1]["heading_after"], 270.0)
        self.assertFalse(attempts[0]["accepted"])
        self.assertTrue(attempts[1]["accepted"])
        self.assertEqual([request["address"] for request in result["random_requests"]], [
            "schelling.turn", "schelling.distance", "schelling.turn", "schelling.distance"
        ])

    def test_own_patch_excludes_self_and_centers_after_acceptance(self):
        case = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
        attempt = next(item for item in result["events"] if item["kind"] == "move_attempt")
        mover = _agent_map(result)["M"]

        self.assertTrue(attempt["details"]["accepted"])
        self.assertAlmostEqual(attempt["details"]["trial_position"][1], 0.1, delta=COORDINATE_TOLERANCE)
        self.assertEqual([mover["x"], mover["y"]], [0.0, 0.0])

    def test_immediate_occupancy_makes_later_actor_retry(self):
        case = next(item for item in cases() if item["case_id"] == "immediate-occupancy-visibility")

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
        attempts = _attempt_projection(result)

        self.assertEqual([item["accepted"] for item in attempts], [True, False, True])
        positions = {(item["x"], item["y"]) for item in result["state"]["agents"]}
        self.assertEqual(len(positions), len(result["state"]["agents"]))

    def test_wrap_trial_is_continuous_then_success_is_centered(self):
        case = next(item for item in cases() if item["case_id"] == "wrap-then-center")

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
        attempt = next(item for item in result["events"] if item["kind"] == "move_attempt")["details"]

        self.assertAlmostEqual(attempt["trial_position"][0], 0.0, delta=COORDINATE_TOLERANCE)
        self.assertAlmostEqual(attempt["trial_position"][1], 0.0, delta=COORDINATE_TOLERANCE)
        self.assertEqual(attempt["patch"], [0, 0])
        self.assertEqual([_agent_map(result)["M"][field] for field in ("x", "y")], [0.0, 0.0])

    def test_weighted_source_metric_keeps_distinct_name_and_value(self):
        case = next(item for item in cases() if item["case_id"] == "weighted-metric-witness")

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])

        self.assertEqual(result["state"]["globals"]["source_similar_sum"], 60)
        self.assertEqual(result["state"]["globals"]["source_total_sum"], 126)
        self.assertAlmostEqual(result["metrics"]["source_percent_similar"], 47.61904761904762, delta=1e-12)
        self.assertNotAlmostEqual(result["metrics"]["source_percent_similar"], 47.125, delta=1e-12)
        self.assertNotIn("percent_similar", result["metrics"])

    def test_zero_denominator_is_a_typed_failure_after_initialization(self):
        case = next(item for item in cases() if item["case_id"] == "zero-denominator")

        with self.assertRaises(AbmRuntimeError) as caught:
            run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])

        self.assertEqual(_error_code(caught.exception), case["expected_error"]["code"])
        self.assertIn(case["expected_error"]["contains"], str(caught.exception).lower())

    def test_before_tick_stop_does_not_override_final_horizon(self):
        case = next(item for item in cases() if item["case_id"] == "stop-versus-horizon")
        plan = compile_model(case["model"]).plan

        horizon = run_abm_plan(plan, random_tape=case["random_tape"])
        longer_model = copy.deepcopy(case["model"])
        longer_model["max_ticks"] = 2
        observed = run_abm_plan(compile_model(longer_model).plan, random_tape=case["random_tape"])

        self.assertEqual((horizon["ticks"], horizon["stop_reason"]), (1, "max_ticks"))
        self.assertEqual((observed["ticks"], observed["stop_reason"]), (1, "condition:all-happy"))


class SchellingSourceInitializationAndTapeTests(unittest.TestCase):
    def test_setup_sprout_uses_patch_identity_and_is_visible_to_later_init_phase(self):
        case = setup_lifecycle_case()

        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])

        self.assertEqual(len(result["state"]["agents"]), 1)
        child = result["state"]["agents"][0]
        self.assertEqual(child["id"], "patch:0:0::setup.sprout::init::source-setup::0")
        self.assertEqual(child["vars"]["group"], "orange")
        self.assertEqual(child["vars"]["heading"], 123.5)
        self.assertTrue(child["vars"]["ready"])
        self.assertTrue(any(event["tick"] == -1 and event["kind"] == "born" for event in result["events"]))

    def test_missing_mismatched_and_extra_tape_entries_are_rejected(self):
        case = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")
        plan = compile_model(case["model"]).plan
        variants = []
        missing = copy.deepcopy(case["random_tape"])
        missing["requests"].pop()
        variants.append((missing, "random_tape_missing"))
        mismatch = copy.deepcopy(case["random_tape"])
        mismatch["requests"][0]["address"] = "wrong.address"
        variants.append((mismatch, "random_tape_mismatch"))
        extra = copy.deepcopy(case["random_tape"])
        extra["requests"].append(copy.deepcopy(extra["requests"][-1]))
        extra["requests"][-1]["occurrence"] = 1
        variants.append((extra, "random_tape_unused"))

        for supplied, code in variants:
            with self.subTest(code=code):
                with self.assertRaises(AbmRuntimeError) as caught:
                    run_abm_plan(plan, random_tape=supplied)
                self.assertEqual(_error_code(caught.exception), code)

    def test_tape_rejects_out_of_domain_value_before_execution(self):
        case = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")
        bad = copy.deepcopy(case["random_tape"])
        bad["requests"][0]["value"] = 360.0

        with self.assertRaises(AbmRuntimeError) as caught:
            run_abm_plan(compile_model(case["model"]).plan, random_tape=bad)

        self.assertEqual(_error_code(caught.exception), "random_tape_mismatch")

    def test_unused_malformed_tape_entries_and_occurrence_overflow_are_rejected_upfront(self):
        case = next(item for item in cases() if item["case_id"] == "pre-step-stop")
        malformed = {
            "schema_version": "abm-random-tape/v1",
            "requests": [
                {
                    "tick": 0,
                    "phase": "never-consumed",
                    "address": "bad",
                    "entity_id": "A",
                    "occurrence": 0,
                    "distribution": "normal",
                    "args": [],
                    "value": 0,
                }
            ],
        }
        occurrence_overflow = copy.deepcopy(malformed)
        occurrence_overflow["requests"][0].update(
            {"distribution": "traversal_key", "occurrence": 2**63, "value": 0.5}
        )

        for supplied in (malformed, occurrence_overflow):
            with self.subTest(supplied=supplied), self.assertRaises(AbmRuntimeError) as caught:
                run_abm_plan(compile_model(case["model"]).plan, random_tape=supplied)
            self.assertEqual(_error_code(caught.exception), "invalid_random_tape")

    def test_retry_budget_exhaustion_is_not_a_silent_fallback(self):
        case = next(item for item in cases() if item["case_id"] == "rejected-attempt-carries-state")
        model = copy.deepcopy(case["model"])
        model["phases"][0]["operations"][0]["local_rejection"]["attempt_budget"] = 1
        one_attempt = copy.deepcopy(case["random_tape"])
        one_attempt["requests"] = one_attempt["requests"][:2]

        with self.assertRaises(AbmRuntimeError) as caught:
            run_abm_plan(compile_model(model).plan, random_tape=one_attempt)

        self.assertEqual(_error_code(caught.exception), "random_attempt_budget_exhausted")

    def test_valid_wrong_selector_is_detected_before_happy_actor_draws(self):
        case = next(item for item in cases() if item["case_id"] == "frozen-membership")
        mutant = copy.deepcopy(case["model"])
        del mutant["phases"][0]["where"]

        with self.assertRaises(AbmRuntimeError) as caught:
            run_abm_plan(compile_model(mutant).plan, random_tape=case["random_tape"])

        self.assertEqual(_error_code(caught.exception), "random_tape_mismatch")

    def test_global_empty_substitution_is_detected_by_random_ledger(self):
        case = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")
        mutant = copy.deepcopy(case["model"])
        operation = mutant["phases"][0]["operations"][0]
        del operation["local_rejection"]
        operation["mode"] = "random_global_empty"
        operation["address"] = "schelling.global-empty"

        with self.assertRaises(AbmRuntimeError) as caught:
            run_abm_plan(compile_model(mutant).plan, random_tape=case["random_tape"])

        self.assertEqual(_error_code(caught.exception), "random_tape_mismatch")


class SchellingSourceContractRejectionTests(unittest.TestCase):
    def test_source_fields_are_rejected_without_versioned_extension(self):
        case = cases()[0]
        without_extension = copy.deepcopy(case["model"])
        del without_extension["source_semantics"]
        selected_without_extension = copy.deepcopy(without_extension)
        selected_without_extension["phases"][0]["where"] = True
        local_without_extension = copy.deepcopy(without_extension)
        local_without_extension["phases"][0].pop("where", None)

        for invalid in (selected_without_extension, local_without_extension):
            with self.subTest(model=invalid["model_id"]), self.assertRaises(CompilationError):
                compile_model(invalid)

    def test_present_optional_source_fields_must_not_be_null(self):
        base = cases()[0]["model"]
        null_extension = copy.deepcopy(base)
        null_extension["source_semantics"] = None
        null_selector = copy.deepcopy(base)
        null_selector["phases"][0]["where"] = None

        for invalid in (null_extension, null_selector):
            with self.subTest(invalid=invalid), self.assertRaises(CompilationError):
                compile_model(invalid)
            with self.assertRaises(CompilationError):
                AbmTickPlan.create(invalid)

    def test_unknown_extension_and_stop_timing_are_rejected_at_compile_and_load(self):
        base = cases()[0]["model"]
        mutations = []
        unknown = copy.deepcopy(base)
        unknown["source_semantics"]["schema_version"] = "abm-source-semantics/v2"
        mutations.append(unknown)
        wrong_timing = copy.deepcopy(base)
        wrong_timing["source_semantics"]["stop_timing"] = "after_tick"
        mutations.append(wrong_timing)
        random_stop = copy.deepcopy(base)
        random_stop["stop_conditions"][0]["when"] = {
            "op": "random",
            "distribution": "bernoulli",
            "address": "invalid.random-stop",
            "args": [0.5],
        }
        mutations.append(random_stop)

        for invalid in mutations:
            with self.subTest(source_semantics=invalid["source_semantics"]):
                with self.assertRaises(CompilationError):
                    compile_model(invalid)
                with self.assertRaises(CompilationError):
                    AbmTickPlan.create(invalid)

    def test_local_rejection_rejects_wrong_topology_phase_mode_bounds_and_budget(self):
        base = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")["model"]
        mutations = []
        finite = copy.deepcopy(base)
        finite["topology"]["kind"] = "finite"
        mutations.append(finite)
        buffered = copy.deepcopy(base)
        buffered["phases"][0]["commit_mode"] = "buffered"
        mutations.append(buffered)
        snapshot = copy.deepcopy(base)
        snapshot["phases"][0]["read_view"] = "phase_start"
        mutations.append(snapshot)
        wrong_turn = copy.deepcopy(base)
        wrong_turn["phases"][0]["operations"][0]["local_rejection"]["turn_bounds"] = [0, 180]
        mutations.append(wrong_turn)
        wrong_distance = copy.deepcopy(base)
        wrong_distance["phases"][0]["operations"][0]["local_rejection"]["distance_bounds"] = [0, 5]
        mutations.append(wrong_distance)
        no_budget = copy.deepcopy(base)
        no_budget["phases"][0]["operations"][0]["local_rejection"]["attempt_budget"] = 0
        mutations.append(no_budget)
        overflow_budget = copy.deepcopy(base)
        overflow_budget["phases"][0]["operations"][0]["local_rejection"]["attempt_budget"] = 2**63
        mutations.append(overflow_budget)

        for invalid in mutations:
            with self.subTest(mutation=mutations.index(invalid)):
                with self.assertRaises(CompilationError):
                    compile_model(invalid)
                with self.assertRaises(CompilationError):
                    AbmTickPlan.create(invalid)

    def test_sprout_is_rejected_outside_patch_initialization(self):
        case = setup_lifecycle_case()
        sprout = copy.deepcopy(case["model"]["source_semantics"]["initialization"][0]["operations"][0])
        ordinary = copy.deepcopy(case["model"])
        ordinary["phases"][0]["operations"] = [sprout]
        agent_init = copy.deepcopy(case["model"])
        agent_init["source_semantics"]["initialization"][0]["target"] = "agents"
        agent_init["source_semantics"]["initialization"][0]["agent_kind"] = "person"

        for invalid in (ordinary, agent_init):
            with self.assertRaises(CompilationError):
                compile_model(invalid)


class SchellingSourceNegativeOracleTests(unittest.TestCase):
    def test_hand_oracle_detects_wrong_stop_attempt_self_center_and_metric_outputs(self):
        selected = {
            item["case_id"]: item
            for item in cases()
            if item["case_id"] in {
                "pre-step-stop",
                "rejected-attempt-carries-state",
                "own-patch-acceptance",
                "weighted-metric-witness",
            }
        }
        results = {
            identity: run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
            for identity, case in selected.items()
        }
        mutants: list[tuple[str, dict]] = []
        wrong_stop = copy.deepcopy(results["pre-step-stop"])
        wrong_stop["ticks"] = 1
        wrong_stop["stop_reason"] = "max_ticks"
        mutants.append(("pre-step-stop", wrong_stop))
        reset_retry = copy.deepcopy(results["rejected-attempt-carries-state"])
        attempts = [item for item in reset_retry["events"] if item["kind"] == "move_attempt"]
        attempts[1]["details"]["patch"] = [4, 0]
        mutants.append(("rejected-attempt-carries-state", reset_retry))
        self_counted = copy.deepcopy(results["own-patch-acceptance"])
        next(item for item in self_counted["events"] if item["kind"] == "move_attempt")["details"]["accepted"] = False
        mutants.append(("own-patch-acceptance", self_counted))
        no_center = copy.deepcopy(results["own-patch-acceptance"])
        _agent_map(no_center)["M"]["y"] = 0.1
        mutants.append(("own-patch-acceptance", no_center))
        wrong_metric = copy.deepcopy(results["weighted-metric-witness"])
        wrong_metric["metrics"]["source_percent_similar"] = 47.125
        mutants.append(("weighted-metric-witness", wrong_metric))

        for identity, mutant in mutants:
            with self.subTest(mutant=identity):
                self.assertTrue(projection_violations(mutant, selected[identity]["projection_expectations"]))


if __name__ == "__main__":
    unittest.main()
