from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import replace

from experiments.simlox_pairing.observations import (
    ObservationError,
    compare_observations,
    extract_engine_observations,
)
from sim_engine_compiler.ir.plan import LEGACY_MINUTE_PHASES, ExecutionPlan
from sim_engine_compiler.reference.simpy_runtime import SimpyReferenceRuntime

TOLERANCES = {
    "event_time": {"equivalent_minutes": 0.006},
    "normal_interval_endpoint": {"equivalent_minutes": 6e-7},
    "profile": {
        field: {"absolute": 1e-8}
        for field in ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")
    },
    "integral": {
        field: {"absolute": 1e-8}
        for field in ("FTMO", "NSYMO", "NSYMA", "NSYMR", "NSYRY")
    },
}


def _plan(starts: tuple[int, ...]) -> ExecutionPlan:
    missions = [
        {
            "index": index,
            "mission_id": f"engine-mission-{index}",
            "name": f"Teaching mission {index}",
            "planned_start": start,
            "preparation_start": start - 60,
            "duration_minutes": 120,
            "required_aircraft": 1,
            "min_required_aircraft": 1,
            "priority": 1,
            "cancel_minutes": 20,
            "success_point": 1.0,
            "required_aircraft_type": "TEACH-AIR",
            "operations_plan_group_id": "teaching-daily",
            "source_path": f"mission_profile.missions[{index}]",
        }
        for index, start in enumerate(starts)
    ]
    activities = [
        {
            "index": index,
            "activity_id": f"teaching-{phase}",
            "name": phase,
            "phase": phase,
            "plan_group_id": "teaching-daily",
            "aircraft_model": "TEACH-AIR",
            "resource_node_index": 0,
            "priority": 1,
            "kind": phase,
            "equipment_component_index": -1,
            "maintenance_methods": [],
            "replacement_ratio": 0.0,
            "steps": [],
            "source_path": f"support_activities.activities[{index}]",
        }
        for index, phase in enumerate(("preflight", "relaunch", "postflight"))
    ]
    return ExecutionPlan.from_dict(
        {
            "plan_version": "aircraft-support-plan/v1alpha2",
            "domain": "aircraft-support",
            "semantic_profile": "legacy-minute-v1",
            "work_policy": "stable-topological-serial",
            "rng_profile": "legacy-sequential-v1",
            "source_inputs_sha256": "a" * 64,
            "duration_minutes": 2160,
            "natural_completion_enabled": False,
            "phases": list(LEGACY_MINUTE_PHASES),
            "aircraft": [
                {
                    "index": 0,
                    "tail_number": "TEACH-AIR-01",
                    "aircraft_type": "TEACH-AIR",
                    "model": "TEACH-AIR",
                    "initial_state": "available",
                }
            ],
            "missions": missions,
            "activities": activities,
            "resource_nodes": [
                {
                    "index": 0,
                    "node_id": "BASE-01",
                    "personnel_capacity": 0,
                    "equipment_capacity": 0,
                    "inventory": [],
                    "organization_node_id": "BASE-01",
                    "source_path": "support_network.nodes[0]",
                }
            ],
            "components": [
                {
                    "index": 0,
                    "component_id": "TEACH-AIR",
                    "name": "Teaching aircraft",
                    "parent_index": -1,
                    "aircraft_indexes": [0],
                    "product_id": "",
                    "product_type": "",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.0,
                    "failure_threshold": 0,
                    "repair_activity_index": -1,
                    "repair_duration_minutes": 0,
                    "source_path": "equipment_tree.components[0]",
                }
            ],
            "preventive_cycles": [],
            "supply_routes": [],
            "unsupported_features": [],
        }
    )


def _identity(starts: tuple[int, ...]) -> dict[str, str]:
    return {
        f"engine-mission-{index}": f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>"
        for index, _start in enumerate(starts)
    }


def _expected_from_observation(observation: dict) -> dict:
    return {
        "case_id": observation["case_id"],
        "events": [
            {
                "kind": event["kind"],
                "time_minutes": event["time_minutes"],
                "mission_instance": event["mission_instance"],
                "aircraft_instance": event["aircraft_instance"],
                "mapping": "state_observable"
                if event["kind"] in {"allocation", "ready_decreased", "ready_increased"}
                else "mission_observable",
            }
            for event in observation["mapped_events"]
        ],
        "intervals": deepcopy(observation["intervals"]),
        "integrals": deepcopy(observation["integrals"]),
        "terminal": deepcopy(observation["terminal"]),
    }


class SimloxPairingObservationTests(unittest.TestCase):
    def _run(self, starts: tuple[int, ...], case_id: str) -> tuple[ExecutionPlan, dict, dict]:
        plan = _plan(starts)
        result = SimpyReferenceRuntime(plan, seed=0).run()
        observation = extract_engine_observations(
            plan,
            result,
            case_id=case_id,
            aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
            mission_identity=_identity(starts),
        )
        return plan, result, observation

    def test_actual_a01_trace_produces_72_expected_state_intervals(self) -> None:
        _plan_value, _result, observation = self._run((480,), "A01")

        self.assertEqual(len(observation["intervals"]), 72)
        self.assertEqual(observation["intervals"][13]["NSYRY"], 1.0)
        for index in (14, 15):
            self.assertEqual(observation["intervals"][index]["NSYMR"], 1.0)
            self.assertEqual(observation["intervals"][index]["NSYRY"], 0.0)
        for index in (16, 17, 18, 19):
            self.assertEqual(observation["intervals"][index]["FTMO"], 1.0)
            self.assertEqual(observation["intervals"][index]["NSYMA"], 1.0)
        self.assertEqual(observation["intervals"][20]["NSYRY"], 1.0)
        self.assertEqual(
            observation["integrals"],
            {
                "FTMO_hours": 2.0,
                "NSYMO_aircraft_hours": 2.0,
                "NSYMA_aircraft_hours": 3.0,
                "NSYMR_aircraft_hours": 1.0,
                "NSYRY_aircraft_hours": 33.0,
            },
        )
        self.assertEqual(
            observation["terminal"],
            {
                "planned_waves": 1,
                "launched_waves": 1,
                "sorties": 1,
                "completed_waves": 1,
                "cancelled_waves": 0,
                "unfinished_at_horizon": 0,
            },
        )
        notification = next(
            event for event in observation["mapped_events"] if event["kind"] == "notification"
        )
        self.assertEqual(notification["time_minutes"], 420)
        self.assertEqual(notification["evidence"]["kind"], "runtime_trace_time_proxy")
        self.assertIn(
            "notification_semantics",
            {item["kind"] for item in observation["unsupported_native_observables"]},
        )

    def test_actual_a02_trace_preserves_each_mission_identity(self) -> None:
        _plan_value, _result, observation = self._run((480, 1200, 1920), "A02")

        self.assertEqual(observation["integrals"]["FTMO_hours"], 6.0)
        self.assertEqual(observation["integrals"]["NSYMR_aircraft_hours"], 3.0)
        self.assertEqual(observation["integrals"]["NSYRY_aircraft_hours"], 27.0)
        starts = [
            event
            for event in observation["mapped_events"]
            if event["kind"] == "start"
        ]
        self.assertEqual([event["time_minutes"] for event in starts], [480, 1200, 1920])
        self.assertEqual(
            [event["mission_instance"] for event in starts],
            list(_identity((480, 1200, 1920)).values()),
        )

    def test_same_integrals_with_wrong_interval_fails_at_first_changed_bin(self) -> None:
        _plan_value, _result, observation = self._run((480,), "A01")
        expected = _expected_from_observation(observation)
        wrong_actual = deepcopy(observation)
        wrong_actual["intervals"][16]["FTMO"], wrong_actual["intervals"][20]["FTMO"] = (
            wrong_actual["intervals"][20]["FTMO"],
            wrong_actual["intervals"][16]["FTMO"],
        )

        comparison = compare_observations(wrong_actual, expected, TOLERANCES)

        self.assertEqual(comparison["status"], "mismatched")
        self.assertEqual(comparison["first_divergence"]["path"], "intervals[16].FTMO")
        self.assertEqual(wrong_actual["integrals"], observation["integrals"])

    def test_equal_duration_shifted_actual_mission_fails_on_event_time_and_bins(self) -> None:
        _correct_plan, _correct_result, correct = self._run((480,), "A01")
        _shifted_plan, _shifted_result, shifted = self._run((510,), "A01")
        expected = _expected_from_observation(correct)

        comparison = compare_observations(shifted, expected, TOLERANCES)

        self.assertEqual(shifted["integrals"], correct["integrals"])
        self.assertEqual(shifted["terminal"], correct["terminal"])
        self.assertEqual(comparison["status"], "mismatched")
        self.assertEqual(
            comparison["first_divergence"]["path"],
            "mapped_events[1].time_minutes",
        )

    def test_wrong_native_identity_fails_even_when_times_and_totals_match(self) -> None:
        _plan_value, _result, observation = self._run((480,), "A01")
        expected = _expected_from_observation(observation)
        wrong_actual = deepcopy(observation)
        wrong_actual["mapped_events"][0]["aircraft_instance"] = "<OTHER-AIRCRAFT,0>"

        comparison = compare_observations(wrong_actual, expected, TOLERANCES)

        self.assertEqual(comparison["status"], "mismatched")
        self.assertIn("aircraft_instance", comparison["first_divergence"]["path"])

    def test_result_from_different_plan_is_rejected_before_observation(self) -> None:
        plan, result, _observation = self._run((480,), "A01")
        result["plan_fingerprint"] = "0" * 64

        with self.assertRaisesRegex(ObservationError, "result_plan_mismatch"):
            extract_engine_observations(
                plan,
                result,
                case_id="A01",
                aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
                mission_identity=_identity((480,)),
            )

    def test_duplicate_native_mission_identity_is_rejected(self) -> None:
        plan = _plan((480, 1200))
        result = SimpyReferenceRuntime(plan, seed=0).run()

        with self.assertRaisesRegex(ObservationError, "identity_not_one_to_one"):
            extract_engine_observations(
                plan,
                result,
                case_id="A02",
                aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
                mission_identity={
                    "engine-mission-0": "<BASIC-MISSION,TEACH-UNIT,0,0,0>",
                    "engine-mission-1": "<BASIC-MISSION,TEACH-UNIT,0,0,0>",
                },
            )

    def test_tampered_terminal_state_is_rejected_against_trace(self) -> None:
        plan = _plan((480,))
        result = SimpyReferenceRuntime(plan, seed=0).run()
        result["terminal_state"]["aircraft"][0]["state"] = "flying"

        with self.assertRaisesRegex(ObservationError, "unexpected_terminal_aircraft_state"):
            extract_engine_observations(
                plan,
                result,
                case_id="A01",
                aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
                mission_identity=_identity((480,)),
            )

    def test_duplicate_terminal_mission_is_rejected_instead_of_overwritten(self) -> None:
        plan = _plan((480,))
        result = SimpyReferenceRuntime(plan, seed=0).run()
        result["terminal_state"]["missions"].append(
            deepcopy(result["terminal_state"]["missions"][0])
        )

        with self.assertRaisesRegex(ObservationError, "terminal_identity_mismatch"):
            extract_engine_observations(
                plan,
                result,
                case_id="A01",
                aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
                mission_identity=_identity((480,)),
            )

    def test_future_semantic_profile_is_rejected_by_bounded_observer(self) -> None:
        plan = replace(_plan((480,)), semantic_profile="future-profile/v1")
        result = SimpyReferenceRuntime(_plan((480,)), seed=0).run()

        with self.assertRaisesRegex(ObservationError, "unsupported_pairing_profile"):
            extract_engine_observations(
                plan,
                result,
                case_id="A01",
                aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
                mission_identity=_identity((480,)),
            )

    def test_unknown_trace_kind_is_rejected_instead_of_silently_ignored(self) -> None:
        plan = _plan((480,))
        result = SimpyReferenceRuntime(plan, seed=0).run()
        result["trace"][1]["kind"] = "future_side_effect"

        with self.assertRaisesRegex(ObservationError, "unsupported_pairing_trace_event"):
            extract_engine_observations(
                plan,
                result,
                case_id="A01",
                aircraft_identity={"TEACH-AIR-01": "<TEACH-AIR-01,0>"},
                mission_identity=_identity((480,)),
            )

    def test_manifest_endpoint_tolerance_accepts_rounding_but_rejects_larger_shift(self) -> None:
        _plan_value, _result, observation = self._run((480,), "A01")
        expected = _expected_from_observation(observation)
        rounded = deepcopy(observation)
        rounded["intervals"][0]["end_minutes"] += 5e-7
        shifted = deepcopy(observation)
        shifted["intervals"][0]["end_minutes"] += 7e-7

        rounded_comparison = compare_observations(rounded, expected, TOLERANCES)
        shifted_comparison = compare_observations(shifted, expected, TOLERANCES)

        self.assertEqual(rounded_comparison["status"], "matched")
        self.assertEqual(shifted_comparison["status"], "mismatched")
        self.assertEqual(
            shifted_comparison["first_divergence"]["path"],
            "intervals[0].end_minutes",
        )

    def test_expected_input_and_plan_pins_are_checked_before_profiles(self) -> None:
        plan, _result, observation = self._run((480,), "A01")
        expected = _expected_from_observation(observation)

        comparison = compare_observations(
            observation,
            expected,
            TOLERANCES,
            expected_source_inputs_sha256="b" * 64,
            expected_plan_fingerprint=plan.fingerprint,
        )

        self.assertEqual(comparison["status"], "mismatched")
        self.assertEqual(
            comparison["first_divergence"]["path"],
            "bindings.source_inputs_sha256",
        )


if __name__ == "__main__":
    unittest.main()
