from __future__ import annotations

import copy
import unittest

from sim_engine_compiler import compile_model, run_abm_batch, run_abm_plan
from sim_engine_compiler.reference import AbmRuntimeError

from tests.conformance.test_abm_ir import base_spec, patch


def get(scope, field):
    return {"op": "get", "scope": scope, "field": field}


def binary(operator, left, right):
    return {"op": "binary", "operator": operator, "left": left, "right": right}


def count(source, *, where=None, agent_kind=None, neighborhood=None):
    return {"op": "count", "source": source, "agent_kind": agent_kind,
            "neighborhood": neighborhood, "where": where}


class FireVerticalSliceTests(unittest.TestCase):
    @staticmethod
    def spec():
        spec = base_spec(width=3)
        spec["model_id"] = "fire-hand-calculable"
        spec["initial_state"]["patches"] = [
            patch(0, 0, status="burning"), patch(1, 0, status="tree"),
            patch(2, 0, status="tree"),
        ]
        burning = binary("==", get("self", "status"), "burning")
        tree_next_to_fire = binary(
            "and", binary("==", get("self", "status"), "tree"),
            binary(">", count("neighbors", neighborhood="von_neumann",
                              where=binary("==", get("self", "status"), "burning")), 0),
        )
        spec["phases"] = [{
            "id": "spread-and-burn", "target": "patches", "agent_kind": None,
            "read_view": "phase_start", "commit_mode": "buffered",
            "traversal": "stable", "random_address": None,
            "operations": [
                {"op": "set", "guard": burning, "target": "self", "field": "status", "value": "burned"},
                {"op": "set", "guard": tree_next_to_fire, "target": "self", "field": "status", "value": "burning"},
            ],
        }]
        spec["stop_conditions"] = [{
            "id": "fire-out",
            "when": binary("==", count("patches", where=binary("!=", get("self", "status"), "burned")), 0),
        }]
        spec["metrics"] = [{
            "id": "burned_patches", "reducer": "count", "source": "patches", "field": None,
            "where": binary("==", get("self", "status"), "burned"), "expression": None,
        }]
        spec["max_ticks"] = 10
        return spec

    def test_fire_spreads_one_cell_per_tick_with_buffered_snapshot(self):
        plan = compile_model(self.spec()).plan

        result = run_abm_plan(plan, seed=11)

        self.assertEqual(result["ticks"], 3)
        self.assertEqual(result["stop_reason"], "condition:fire-out")
        self.assertEqual([item["vars"]["status"] for item in result["state"]["patches"]],
                         ["burned", "burned", "burned"])
        self.assertEqual(result["metrics"], {"burned_patches": 3})
        changes = [(event["tick"], event["entity"], event["details"]["after"])
                   for event in result["events"] if event["kind"] == "set"]
        self.assertEqual(changes, [
            (0, "patch:0:0", "burned"), (0, "patch:1:0", "burning"),
            (1, "patch:1:0", "burned"), (1, "patch:2:0", "burning"),
            (2, "patch:2:0", "burned"),
        ])

    def test_repeat_seed_produces_complete_identical_result(self):
        plan = compile_model(self.spec()).plan
        self.assertEqual(run_abm_plan(plan, seed=9), run_abm_plan(plan, seed=9))


class SchellingStyleTests(unittest.TestCase):
    def test_random_traversal_and_local_empty_move_are_named_and_deterministic(self):
        spec = base_spec(width=3)
        spec["model_id"] = "schelling-local-move"
        spec["initial_state"]["agents"] = [
            {"id": "person-red", "kind": "person", "x": 1.0, "y": 0.0, "vars": {"group": "red"}},
            {"id": "person-blue", "kind": "person", "x": 0.0, "y": 0.0, "vars": {"group": "blue"}},
        ]
        spec["phases"] = [{
            "id": "relocate", "target": "agents", "agent_kind": "person",
            "read_view": "current", "commit_mode": "immediate", "traversal": "random",
            "random_address": "schelling.relocation-order",
            "operations": [{"op": "move", "guard": binary("==", get("self", "group"), "red"),
                            "mode": "random_empty", "x": None, "y": None,
                            "neighborhood": "moore", "address": "schelling.empty-neighbor",
                            "heading_step": None}],
        }]

        result = run_abm_plan(compile_model(spec).plan, seed=3)

        red = next(item for item in result["state"]["agents"] if item["id"] == "person-red")
        self.assertEqual((red["x"], red["y"]), (2, 0))
        self.assertEqual(
            [(item["address"], item["entity_id"], item["distribution"])
             for item in result["random_requests"]],
            [
                ("schelling.relocation-order", "person-blue", "traversal_key"),
                ("schelling.relocation-order", "person-red", "traversal_key"),
                ("schelling.empty-neighbor", "person-red", "integer"),
            ],
        )

    def test_named_random_expression_records_stable_business_identity(self):
        spec = base_spec()
        spec["initial_state"]["agents"] = [
            {"id": "person-business-id", "kind": "person", "x": 0.0, "y": 0.0, "vars": {}},
        ]
        spec["phases"] = [{
            "id": "sample", "target": "agents", "agent_kind": None,
            "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
            "random_address": None,
            "operations": [{"op": "set", "guard": None, "target": "self", "field": "draw",
                            "value": {"op": "random", "distribution": "uniform",
                                      "address": "person.draw", "args": [0.0, 1.0]}}],
        }]
        plan = compile_model(spec).plan

        first = run_abm_plan(plan, seed=17)
        second = run_abm_plan(plan, seed=17)

        self.assertEqual(first, second)
        self.assertEqual(first["random_requests"][0]["entity_id"], "person-business-id")
        self.assertEqual(first["random_requests"][0]["address"], "person.draw")

    def test_batch_isolated_state_repeated_seed_and_input_order_are_stable(self):
        plan = compile_model(base_spec()).plan
        requests = [{"sample_index": 9, "seed": 4}, {"sample_index": 2, "seed": 4}]

        one_worker = run_abm_batch(plan, requests, workers=1)
        four_workers = run_abm_batch(plan, list(reversed(requests)), workers=4)

        self.assertEqual(one_worker, four_workers)
        self.assertEqual([item["sample_index"] for item in one_worker], [2, 9])
        self.assertEqual(one_worker[0]["result"], one_worker[1]["result"])


class SchellingAdaptationTests(unittest.TestCase):
    def test_global_empty_sequential_move_outer_neighbor_binding_and_ratio_metric(self):
        spec = base_spec(width=4)
        spec["model_id"] = "schelling-global-empty-adaptation"
        spec["initial_state"]["agents"] = [
            {"id": "red-a", "kind": "person", "x": 0.0, "y": 0.0,
             "vars": {"group": "red", "happy": False}},
            {"id": "blue", "kind": "person", "x": 1.0, "y": 0.0,
             "vars": {"group": "blue", "happy": False}},
            {"id": "red-b", "kind": "person", "x": 2.0, "y": 0.0,
             "vars": {"group": "red", "happy": False}},
        ]
        similar_neighbors = count(
            "neighbors", agent_kind="*", neighborhood="moore",
            where=binary("==", get("self", "group"), get("outer", "group")),
        )
        assess = {
            "op": "set", "guard": None, "target": "self", "field": "happy",
            "value": binary(">", similar_neighbors, 0),
        }
        spec["phases"] = [
            {
                "id": "assess-at-tick-start", "target": "agents", "agent_kind": "person",
                "read_view": "phase_start", "commit_mode": "buffered", "traversal": "stable",
                "random_address": None, "operations": [assess],
            },
            {
                "id": "move-unhappy-sequentially", "target": "agents", "agent_kind": "person",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{
                    "op": "move", "guard": {"op": "unary", "operator": "not",
                                              "value": get("self", "happy")},
                    "mode": "random_global_empty", "x": None, "y": None,
                    "neighborhood": None, "address": "schelling.global-empty",
                    "heading_step": None,
                }],
            },
            {
                "id": "reassess-at-phase-end", "target": "agents", "agent_kind": "person",
                "read_view": "phase_start", "commit_mode": "buffered", "traversal": "stable",
                "random_address": None, "operations": [assess],
            },
        ]
        happy_count = count("agents", where=binary("==", get("self", "happy"), True))
        spec["metrics"] = [{
            "id": "percent_happy", "reducer": "expression", "source": "globals",
            "field": None, "where": None,
            "expression": binary("*", binary("/", happy_count, count("agents")), 100.0),
        }]

        result = run_abm_plan(compile_model(spec).plan, seed=21)

        positions = [(item["x"], item["y"]) for item in result["state"]["agents"]]
        self.assertEqual(len(set(positions)), 3)
        moves = [item for item in result["events"] if item["kind"] == "moved"]
        self.assertEqual([item["entity"] for item in moves], ["blue", "red-a", "red-b"])
        self.assertEqual(
            [item["address"] for item in result["random_requests"]],
            ["schelling.global-empty"] * 3,
        )
        happy = sum(item["vars"]["happy"] for item in result["state"]["agents"])
        self.assertEqual(result["metrics"]["percent_happy"], happy / 3 * 100.0)


class WolfSheepStyleTests(unittest.TestCase):
    def test_continuous_torus_patch_update_birth_death_and_newborn_deferral(self):
        spec = base_spec(width=2, topology="torus")
        spec["model_id"] = "wolf-sheep-lifecycle"
        spec["initial_state"]["patches"] = [patch(0, 0, grass=2), patch(1, 0, grass=0)]
        spec["initial_state"]["agents"] = [
            {"id": "sheep-1", "kind": "sheep", "x": 1.4, "y": 0.0, "vars": {"energy": 1}},
        ]
        spec["phases"] = [
            {
                "id": "move-and-graze", "target": "agents", "agent_kind": "sheep",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [
                    {"op": "move", "guard": None, "mode": "offset", "x": 0.2, "y": 0.0,
                     "neighborhood": None, "address": None, "heading_step": None},
                    {"op": "increment", "guard": None, "target": "patch_here", "field": "grass", "value": -1},
                    {"op": "birth", "guard": binary(">", get("self", "energy"), 0), "kind": "sheep",
                     "count": 1, "vars": {"energy": 0}, "address": "sheep.reproduce",
                     "child_move": None},
                    {"op": "death", "guard": None, "mode": "self", "agent_kind": None,
                     "address": None},
                ],
            },
            {
                "id": "newborn-must-wait", "target": "agents", "agent_kind": "sheep",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "increment", "guard": None, "target": "self",
                                "field": "energy", "value": 10}],
            },
        ]
        spec["max_ticks"] = 1

        result = run_abm_plan(compile_model(spec).plan)

        self.assertEqual([item["id"] for item in result["state"]["agents"]],
                         ["sheep-1::sheep.reproduce::0::0"])
        self.assertEqual(result["state"]["agents"][0]["vars"]["energy"], 0)
        self.assertAlmostEqual(result["state"]["agents"][0]["x"], -0.4, places=15)
        self.assertEqual([item["vars"]["grass"] for item in result["state"]["patches"]], [1, 0])
        self.assertEqual([item["kind"] for item in result["events"]],
                         ["moved", "increment", "born", "died"])

    def test_finite_grid_rejects_out_of_bounds_continuous_move(self):
        spec = base_spec()
        spec["initial_state"]["agents"] = [
            {"id": "wolf", "kind": "wolf", "x": 0.0, "y": 0.0, "vars": {}},
        ]
        spec["phases"] = [{
            "id": "escape", "target": "agents", "agent_kind": None,
            "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
            "random_address": None,
            "operations": [{"op": "move", "guard": None, "mode": "offset", "x": 1, "y": 0,
                            "neighborhood": None, "address": None, "heading_step": None}],
        }]

        with self.assertRaisesRegex(AbmRuntimeError, "out of bounds"):
            run_abm_plan(compile_model(spec).plan)


class WolfSheepLifecycleTests(unittest.TestCase):
    def test_predation_heading_grass_birth_self_death_stop_and_newborn_deferral(self):
        spec = base_spec(width=3, topology="torus")
        spec["model_id"] = "wolf-sheep-complete-lifecycle-slice"
        spec["initial_state"]["patches"] = [
            patch(0, 0, grass=2), patch(1, 0, grass=0), patch(2, 0, grass=0),
        ]
        spec["initial_state"]["agents"] = [
            {"id": "wolf-1", "kind": "wolf", "x": 0.0, "y": 0.0,
             "vars": {"energy": 2, "heading": 0.0}},
            {"id": "sheep-a", "kind": "sheep", "x": 0.0, "y": 0.0,
             "vars": {"energy": -1, "heading": 0.0}},
            {"id": "sheep-b", "kind": "sheep", "x": 0.0, "y": 0.0,
             "vars": {"energy": -1, "heading": 0.0}},
        ]
        spec["phases"] = [
            {
                "id": "sheep-graze", "target": "agents", "agent_kind": "sheep",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "increment", "guard": None, "target": "patch_here",
                                "field": "grass", "value": -1}],
            },
            {
                "id": "wolf-heading-step", "target": "agents", "agent_kind": "wolf",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{
                    "op": "move", "guard": None, "mode": "heading_step", "x": None, "y": None,
                    "neighborhood": None, "address": None,
                    "heading_step": {"right_max": 50, "left_max": 50, "distance": 0.0,
                                     "right_address": "wolf.turn-right",
                                     "left_address": "wolf.turn-left"},
                }],
            },
            {
                "id": "wolf-predation", "target": "agents", "agent_kind": "wolf",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [
                    {"op": "death", "guard": binary(">", count("agents_here", agent_kind="sheep"), 0),
                     "mode": "random_agent_here", "agent_kind": "sheep",
                     "address": "wolf.choose-prey"},
                    {"op": "increment", "guard": None, "target": "self", "field": "energy", "value": 4},
                ],
            },
            {
                "id": "wolf-reproduction", "target": "agents", "agent_kind": "wolf",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{
                    "op": "birth", "guard": binary(">", get("self", "energy"), 5),
                    "kind": "wolf", "count": 1, "vars": {"energy": 1},
                    "address": "wolf.reproduce",
                    "child_move": {"heading": 360.0, "address": "wolf.child-heading", "distance": 0.2},
                }],
            },
            {
                "id": "sheep-starvation", "target": "agents", "agent_kind": "sheep",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "death", "guard": binary("<", get("self", "energy"), 0),
                                "mode": "self", "agent_kind": None, "address": None}],
            },
            {
                "id": "newborn-deferred", "target": "agents", "agent_kind": "wolf",
                "read_view": "current", "commit_mode": "immediate", "traversal": "stable",
                "random_address": None,
                "operations": [{"op": "increment", "guard": None, "target": "self",
                                "field": "energy", "value": 10}],
            },
        ]
        spec["stop_conditions"] = [{
            "id": "sheep-extinct", "when": binary("==", count("agents", agent_kind="sheep"), 0),
        }]
        spec["metrics"] = [
            {"id": "grass_total", "reducer": "sum", "source": "patches", "field": "grass",
             "where": None, "expression": None},
            {"id": "wolf_count", "reducer": "expression", "source": "globals", "field": None,
             "where": None, "expression": count("agents", agent_kind="wolf")},
        ]
        spec["max_ticks"] = 5

        result = run_abm_plan(compile_model(spec).plan, seed=8)

        self.assertEqual(result["stop_reason"], "condition:sheep-extinct")
        self.assertEqual(result["ticks"], 1)
        self.assertEqual(result["metrics"], {"grass_total": 0, "wolf_count": 2})
        wolves = {item["id"]: item for item in result["state"]["agents"]}
        self.assertEqual(wolves["wolf-1"]["vars"]["energy"], 16)
        child_id = "wolf-1::wolf.reproduce::0::0"
        self.assertEqual(wolves[child_id]["vars"]["energy"], 1)
        self.assertIn("heading", wolves[child_id]["vars"])
        self.assertNotEqual(wolves["wolf-1"]["vars"]["heading"], 0.0)
        died = [item for item in result["events"] if item["kind"] == "died"]
        self.assertEqual(len(died), 2)
        self.assertEqual(sum("by" in item["details"] for item in died), 1)
        self.assertEqual(
            [item["address"] for item in result["random_requests"]],
            ["wolf.turn-right", "wolf.turn-left", "wolf.choose-prey", "wolf.child-heading"],
        )


if __name__ == "__main__":
    unittest.main()
