from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence
from sim_engine_compiler.reference.simpy_runtime import JobRuntimeState


ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = ROOT / "tests" / "fixtures" / "synthetic"


class B2PreventiveTests(unittest.TestCase):
    def test_failure_exposure_advances_only_while_aircraft_is_flying(self):
        inputs = json.loads((SYNTHETIC / "b2-failure-repair.json").read_text())
        runtime = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0)
        aircraft = runtime.aircraft[0]
        aircraft.failure_remaining[(1, 0)] = 0.5

        runtime._phase_failures()

        self.assertEqual(aircraft.failure_remaining[(1, 0)], 0.5)
        self.assertNotIn((1, 0), aircraft.instance_failure_minutes)

        aircraft.state = "flying"
        runtime.minute = 1
        runtime._phase_failures()

        self.assertEqual(aircraft.failure_remaining[(1, 0)], -0.5)
        self.assertEqual(aircraft.instance_failure_minutes[(1, 0)], 1)

    def test_repair_only_clears_the_target_component_failure(self):
        inputs = json.loads((SYNTHETIC / "b2-failure-repair.json").read_text())
        inputs["equipment_tree"]["components"].append(
            {
                "id": "auxiliary-lru",
                "name": "Auxiliary LRU",
                "parent_id": "f35",
                "aircraft_model": "F35",
                "product_id": "spare-auxiliary",
                "product_type": "LRU",
                "quantity": 1,
                "failure_distribution": {"distributionType": "exponential", "rate": 20},
            }
        )
        generic_repair = copy.deepcopy(
            inputs["support_activities"]["activities"][-1]
        )
        generic_repair["id"] = "generic-corrective"
        generic_repair["name"] = "Generic corrective repair"
        generic_repair.pop("equipment_id")
        inputs["support_activities"]["activities"].append(generic_repair)
        runtime = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0)
        aircraft = runtime.aircraft[0]
        aircraft.instance_failure_minutes = {(1, 0): 4, (2, 0): 5}
        aircraft.failure_remaining = {(1, 0): 12.0, (2, 0): 0.0}
        job = JobRuntimeState(
            job_id="repair-test",
            aircraft_index=0,
            kind="repair",
            activity_index=0,
            mission_index=None,
            component_index=1,
            component_instance_index=0,
        )

        runtime._complete_job(job)

        self.assertEqual(aircraft.instance_failure_minutes, {(2, 0): 5})
        self.assertTrue(aircraft.in_flight_failure)
        self.assertEqual(aircraft.state, "maintenance")
        self.assertGreater(aircraft.failure_remaining[(1, 0)], 0.0)
        self.assertEqual(aircraft.failure_remaining[(2, 0)], 0.0)
        self.assertEqual(runtime.jobs[-1].component_index, 2)
        self.assertEqual(runtime.jobs[-1].component_instance_index, 0)

        runtime._complete_job(runtime.jobs[-1])

        self.assertEqual(aircraft.instance_failure_minutes, {})
        self.assertFalse(aircraft.in_flight_failure)
        self.assertEqual(aircraft.state, "available")

        requests_before = len(runtime.sample_requests)
        broken_job = JobRuntimeState(
            job_id="repair-broken-identity",
            aircraft_index=0,
            kind="repair",
            activity_index=0,
            mission_index=None,
            component_index=1,
        )
        with self.assertRaises(RuntimeError):
            runtime._complete_job(broken_job)
        self.assertEqual(len(runtime.sample_requests), requests_before)
        self.assertEqual(aircraft.state, "available")

    def test_quantity_instances_fail_and_repair_independently(self):
        inputs = json.loads((SYNTHETIC / "b2-failure-repair.json").read_text())
        component = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "radar-lru"
        )
        component["quantity"] = 2
        runtime = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0)
        aircraft = runtime.aircraft[0]

        self.assertEqual(runtime._failure_instance_slots[0], ((1, 0), (1, 1)))
        self.assertIn((1, 0), aircraft.failure_remaining)
        self.assertIn((1, 1), aircraft.failure_remaining)
        initialize = [
            request
            for request in runtime.sample_requests
            if request["reason"] == "initialize"
            and request["component_id"] == "radar-lru"
            and request["entity"] == aircraft.tail_number
        ]
        self.assertEqual(
            [request["instance_index"] for request in initialize], [0, 1]
        )
        self.assertTrue(
            all(
                request["quantity_index"] == request["instance_index"]
                for request in initialize
            )
        )

        aircraft.failure_remaining[(1, 0)] = 0.5
        aircraft.failure_remaining[(1, 1)] = 30.5
        aircraft.state = "flying"
        runtime.minute = 5
        runtime._phase_failures()

        self.assertEqual(aircraft.instance_failure_minutes, {(1, 0): 5})
        self.assertEqual(aircraft.failure_remaining[(1, 1)], 30.5)
        self.assertEqual(aircraft.failed_component_index, 1)
        self.assertEqual(aircraft.failed_component_instance_index, 0)
        self.assertTrue(aircraft.in_flight_failure)
        self.assertEqual(aircraft.state, "maintenance")
        repair_job = runtime.jobs[-1]
        self.assertEqual((repair_job.component_index, repair_job.component_instance_index), (1, 0))

        requests_before = len(runtime.sample_requests)
        runtime._complete_job(repair_job)

        self.assertEqual(len(runtime.sample_requests), requests_before + 1)
        last_request = runtime.sample_requests[-1]
        self.assertEqual(last_request["reason"], "repair_completed")
        self.assertEqual(last_request["instance_index"], 0)
        self.assertEqual(aircraft.instance_failure_minutes, {})
        self.assertEqual(aircraft.failure_remaining[(1, 1)], 30.5)
        self.assertFalse(aircraft.in_flight_failure)
        self.assertEqual(aircraft.state, "available")

        aircraft.instance_failure_minutes = {(1, 0): 7, (1, 1): 8}
        aircraft.in_flight_failure = True
        first_job = JobRuntimeState(
            job_id="repair-instance-0",
            aircraft_index=0,
            kind="repair",
            activity_index=runtime.plan.components[1].repair_activity_index,
            mission_index=None,
            component_index=1,
            component_instance_index=0,
        )
        runtime._complete_job(first_job)

        self.assertEqual(aircraft.instance_failure_minutes, {(1, 1): 8})
        self.assertTrue(aircraft.in_flight_failure)
        self.assertEqual(aircraft.state, "maintenance")
        self.assertEqual(aircraft.failed_component_instance_index, 1)
        chained_job = runtime.jobs[-1]
        self.assertEqual(
            (chained_job.component_index, chained_job.component_instance_index), (1, 1)
        )

        runtime._complete_job(chained_job)

        self.assertEqual(aircraft.instance_failure_minutes, {})
        self.assertFalse(aircraft.in_flight_failure)
        self.assertEqual(aircraft.state, "available")

    def test_component_failure_view_keeps_earliest_instance_minute(self):
        inputs = json.loads((SYNTHETIC / "b2-failure-repair.json").read_text())
        component = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "radar-lru"
        )
        component["quantity"] = 2
        runtime = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0)
        aircraft = runtime.aircraft[0]
        aircraft.instance_failure_minutes = {(1, 1): 9, (1, 0): 6}

        self.assertEqual(
            runtime._component_failure_view(aircraft), {"radar-lru": 6}
        )

    def test_same_minute_instance_failures_count_as_one_failed_component(self):
        inputs = json.loads((SYNTHETIC / "b2-failure-repair.json").read_text())
        root = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "f35"
        )
        root["failure_threshold"] = 2
        radar = next(
            item for item in inputs["equipment_tree"]["components"]
            if item["id"] == "radar-lru"
        )
        radar["quantity"] = 2
        inputs["equipment_tree"]["components"].append(
            {
                "id": "auxiliary-lru",
                "name": "Auxiliary LRU",
                "parent_id": "f35",
                "aircraft_model": "F35",
                "product_id": "spare-auxiliary",
                "product_type": "LRU",
                "quantity": 1,
                "failure_distribution": {"distributionType": "exponential", "rate": 20},
            }
        )
        runtime = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0)
        aircraft = runtime.aircraft[0]
        self.assertEqual(
            runtime._failure_instance_slots[0], ((1, 0), (1, 1), (2, 0))
        )

        aircraft.state = "flying"
        aircraft.failure_remaining[(1, 0)] = 0.5
        aircraft.failure_remaining[(1, 1)] = 0.4
        aircraft.failure_remaining[(2, 0)] = 500.0
        runtime.minute = 8
        runtime._phase_failures()

        self.assertEqual(
            aircraft.instance_failure_minutes, {(1, 0): 8, (1, 1): 8}
        )
        self.assertEqual(aircraft.failure_remaining[(2, 0)], 499.0)
        self.assertEqual(aircraft.state, "flying")
        self.assertFalse(aircraft.in_flight_failure)
        component_failed = [
            event for event in runtime.trace if event["kind"] == "component_failed"
        ]
        self.assertEqual(
            [
                (event["details"]["component_id"], event["details"]["instance_index"])
                for event in component_failed
            ],
            [("radar-lru", 0), ("radar-lru", 1)],
        )
        self.assertFalse(
            [event for event in runtime.trace if event["kind"] == "aircraft_failed"]
        )
        self.assertFalse(runtime._failure_reaches_root(0))
        aircraft.instance_failure_minutes[(2, 0)] = 8
        self.assertTrue(runtime._failure_reaches_root(0))
        aircraft.instance_failure_minutes.pop((2, 0))

        runtime._return_aircraft(0, early_return=False)

        self.assertEqual(aircraft.state, "maintenance")
        repair_job = runtime.jobs[-1]
        self.assertEqual(
            (repair_job.component_index, repair_job.component_instance_index), (1, 0)
        )
        requests_before = len(runtime.sample_requests)
        runtime._complete_job(repair_job)

        self.assertEqual(aircraft.instance_failure_minutes, {(1, 1): 8})
        chained_job = runtime.jobs[-1]
        self.assertEqual(
            (chained_job.component_index, chained_job.component_instance_index), (1, 1)
        )
        runtime._complete_job(chained_job)

        self.assertEqual(aircraft.instance_failure_minutes, {})
        self.assertEqual(aircraft.state, "available")
        self.assertEqual(len(runtime.sample_requests), requests_before + 2)
        resamples = [
            request
            for request in runtime.sample_requests
            if request["reason"] == "repair_completed"
        ]
        self.assertEqual([request["instance_index"] for request in resamples], [0, 1])

    def test_initial_calendar_due_matches_oracle(self):
        inputs = json.loads((SYNTHETIC / "b2-preventive-maintenance.json").read_text())
        oracle = json.loads(
            (SYNTHETIC / "b2-preventive-maintenance-oracle.json").read_text()
        )
        result = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0).run()
        self.assertIsNone(first_divergence(oracle["terminal_state"], result["terminal_state"]))
        self.assertEqual(oracle["metrics"]["spare_fill_rate"], result["metrics"]["spare_fill_rate"])
        expected = [
            (item["time"], item["phase"], item["kind"], item["entity"])
            for item in oracle["trace"]
            if item["kind"] in {"preventive_completed", "simulation_stopped"}
        ]
        actual = [
            (item["time"], item["phase"], item["kind"], item["entity"])
            for item in result["trace"]
            if item["kind"] in {"preventive_completed", "simulation_stopped"}
        ]
        self.assertIsNone(first_divergence(expected, actual))


class B3OrganizationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = json.loads((SYNTHETIC / "b3-upstream-transport.json").read_text())
        cls.oracle = json.loads(
            (SYNTHETIC / "b3-upstream-transport-oracle.json").read_text()
        )
        cls.result = SimpyReferenceRuntime(
            compile_aircraft_support(cls.inputs), seed=0
        ).run()

    def test_vertical_supply_transport_wakeup_and_ledgers_match_oracle(self):
        self.assertIsNone(
            first_divergence(self.oracle["terminal_state"], self.result["terminal_state"])
        )
        kinds = {
            "organization_supply_selected",
            "organization_transport_dispatched",
            "spare_request",
            "spare_shortage",
            "transport_arrived",
            "organization_transport_arrived",
            "spare_consumed",
            "preventive_completed",
            "simulation_stopped",
        }

        def timeline(trace):
            return [
                (item["time"], item["phase"], item["kind"])
                for item in trace
                if item["kind"] in kinds
            ]

        self.assertIsNone(
            first_divergence(timeline(self.oracle["trace"]), timeline(self.result["trace"]))
        )
        for key in (
            "spare_stock_total",
            "spare_demand_total",
            "spare_immediately_filled_total",
            "spare_consumed_total",
            "shortage_events",
            "transport_in_transit_count",
            "transport_replenishment_events",
            "total_transport_delay_minutes",
            "mean_transport_delay",
        ):
            self.assertEqual(self.oracle["metrics"][key], self.result["metrics"][key])

    def test_lateral_route_is_precompiled_and_executed(self):
        inputs = copy.deepcopy(self.inputs)
        graph = inputs["support_network"]["organization_graph"]
        graph["runtime_mode"] = "vertical_lateral"
        graph["nodes"] = [
            {"id": "root", "name": "Root", "parent_id": None},
            {"id": "base", "name": "Base", "parent_id": "root"},
            {"id": "line", "name": "Flight line", "parent_id": "root"},
        ]
        graph["parent_edges"] = [
            {"from_node_id": "root", "to_node_id": "base"},
            {"from_node_id": "root", "to_node_id": "line"},
        ]
        graph["lateral_edges"] = [{
            "id": "base-to-line",
            "from_node_id": "base",
            "to_node_id": "line",
            "priority": 1,
            "enabled": True,
        }]
        plan = compile_aircraft_support(inputs)
        self.assertEqual(plan.supply_routes[0].supply_mode, "lateral")
        result = SimpyReferenceRuntime(plan, seed=0).run()
        selected = next(
            item for item in result["trace"] if item["kind"] == "organization_supply_selected"
        )
        self.assertEqual(selected["details"]["supply_mode"], "lateral")
        self.assertEqual(selected["details"]["relation_id"], "base-to-line")
        self.assertEqual(result["metrics"]["spare_consumed_total"], 1)

    def test_cancelled_waiting_job_returns_arrived_reservation(self):
        inputs = json.loads((SYNTHETIC / "b1-daily-operations.json").read_text())
        inputs["time"]["duration_minutes"] = 8
        inputs["mission_profile"]["duration_minutes"] = 8
        inputs["mission_profile"]["basic_missions"][0].update(
            {"advanceNoticeMinutes": 2, "cancelMinutes": 1}
        )
        inputs["mission_profile"]["composite_tasks"][0]["taskItems"] = [
            {
                "id": "cancelled-sortie",
                "basicMissionId": "basic-sortie",
                "basicTaskName": "Cancelled sortie",
                "firstWaveTime": "00:03",
                "dailyRepeatCount": 1,
                "equipmentType": "F35",
                "operations_plan_group_id": "f35-daily",
            }
        ]
        inputs["aircraft"]["fleet_count"] = 1
        inputs["aircraft"]["assets"] = inputs["aircraft"]["assets"][:1]
        inputs["support_network"] = copy.deepcopy(self.inputs["support_network"])
        for node in inputs["support_network"]["nodes"]:
            node["personnel_capacity"] = 0
            node["equipment_capacity"] = 0
        for activity in inputs["support_activities"]["activities"]:
            activity["resource_id"] = "line"
        preflight = inputs["support_activities"]["activities"][0]
        preflight["resource_id"] = "line"
        preflight["jobs"][0]["durationMinutes"] = 10
        preflight["jobs"][0]["spare"] = "filter,1"
        result = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0).run()
        returns = [
            item
            for item in result["trace"]
            if item["kind"] == "organization_spare_reservation_returned"
        ]
        self.assertEqual([(item["time"], item["phase"]) for item in returns], [(5, "transport_arrivals")])
        self.assertEqual(result["terminal_state"]["jobs"][0]["state"], "cancelled")
        inventories = {
            item["node_id"]: item["inventory"] for item in result["terminal_state"]["resources"]
        }
        self.assertEqual(inventories, {"base": {"filter": 0}, "line": {"filter": 1}})


if __name__ == "__main__":
    unittest.main()
