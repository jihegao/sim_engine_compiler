from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = ROOT / "tests" / "fixtures" / "synthetic"


class B2PreventiveTests(unittest.TestCase):
    def test_initial_calendar_due_matches_oracle(self):
        inputs = json.loads((SYNTHETIC / "b2-preventive-maintenance.json").read_text())
        oracle = json.loads(
            (SYNTHETIC / "b2-preventive-maintenance-oracle.json").read_text()
        )
        result = SimpyReferenceRuntime(compile_aircraft_support(inputs), seed=0).run()
        self.assertIsNone(first_divergence(oracle["terminal_state"], result["terminal_state"]))
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
