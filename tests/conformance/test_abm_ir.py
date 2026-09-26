from __future__ import annotations

import copy
import unittest

from sim_engine_compiler import compile_model
from sim_engine_compiler.compiler.registry import registration_for
from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.ir.abm import (
    ABM_BUSINESS_VERSION, ABM_CORE_VERSION, ABM_PLAN_VERSION, AbmTickPlan,
)


def patch(x, y, **variables):
    return {"id": f"patch:{x}:{y}", "x": x, "y": y, "vars": variables}


def base_spec(*, width=1, height=1, topology="finite"):
    return {
        "model_id": "test-model",
        "profile": "abm-tick-v1",
        "topology": {"kind": topology, "width": width, "height": height},
        "initial_state": {
            "globals": {},
            "patches": [patch(x, y) for x in range(width) for y in range(height)],
            "agents": [],
        },
        "phases": [{
            "id": "noop", "target": "patches", "agent_kind": None,
            "read_view": "phase_start", "commit_mode": "buffered",
            "traversal": "stable", "random_address": None,
            "operations": [{"op": "set", "guard": False, "target": "self",
                            "field": "unused", "value": 0}],
        }],
        "stop_conditions": [],
        "metrics": [],
        "max_ticks": 1,
    }


class AbmIrContractTests(unittest.TestCase):
    def test_compile_model_returns_three_reloadable_layers_and_lineage(self):
        spec = base_spec(width=2)

        business, core, plan, lineage = compile_model(spec)

        self.assertEqual(business.to_dict()["version"], ABM_BUSINESS_VERSION)
        self.assertEqual(core.to_dict()["version"], ABM_CORE_VERSION)
        self.assertEqual(plan.to_dict()["version"], ABM_PLAN_VERSION)
        self.assertEqual(AbmTickPlan.from_dict(plan.to_dict()), plan)
        self.assertEqual(lineage["business_fingerprint"], business.fingerprint)
        self.assertEqual(lineage["core_fingerprint"], core.fingerprint)
        self.assertEqual(lineage["plan_fingerprint"], plan.fingerprint)
        self.assertEqual([item["id"] for item in lineage["symbols"][:2]],
                         ["patch:0:0", "patch:1:0"])

    def test_registry_selects_versions_without_domain_branching(self):
        registration = registration_for("abm-tick-v1")

        self.assertEqual(registration.business_version, ABM_BUSINESS_VERSION)
        self.assertEqual(registration.core_version, ABM_CORE_VERSION)
        self.assertEqual(registration.plan_version, ABM_PLAN_VERSION)
        self.assertIsNotNone(registration.runtime_factory)

    def test_unknown_profile_topology_operation_traversal_and_random_are_rejected(self):
        mutations = []
        unknown_profile = base_spec()
        unknown_profile["profile"] = "abm-event-v1"
        mutations.append(unknown_profile)
        unknown_topology = base_spec()
        unknown_topology["topology"]["kind"] = "hex"
        mutations.append(unknown_topology)
        unknown_operation = base_spec()
        unknown_operation["phases"][0]["operations"][0]["op"] = "eval-python"
        mutations.append(unknown_operation)
        unknown_traversal = base_spec()
        unknown_traversal["phases"][0]["traversal"] = "implementation-order"
        mutations.append(unknown_traversal)
        unknown_random = base_spec()
        unknown_random["phases"][0]["operations"][0]["value"] = {
            "op": "random", "distribution": "normal", "address": "bad", "args": [0, 1]
        }
        mutations.append(unknown_random)
        unknown_move = base_spec()
        unknown_move["phases"][0]["operations"] = [{
            "op": "move", "guard": None, "mode": "teleport", "x": None, "y": None,
            "neighborhood": None, "address": None, "heading_step": None,
        }]
        mutations.append(unknown_move)
        unknown_death = base_spec()
        unknown_death["phases"][0]["operations"] = [{
            "op": "death", "guard": None, "mode": "all_agents", "agent_kind": None,
            "address": None,
        }]
        mutations.append(unknown_death)

        for invalid in mutations:
            with self.subTest(invalid=invalid):
                with self.assertRaises(CompilationError):
                    compile_model(invalid)

    def test_plan_load_rejects_checksum_and_unknown_update_semantics(self):
        plan = compile_model(base_spec()).plan.to_dict()
        damaged = copy.deepcopy(plan)
        damaged["payload"]["max_ticks"] = 2
        with self.assertRaisesRegex(CompilationError, "checksum mismatch"):
            AbmTickPlan.from_dict(damaged)

        invalid = copy.deepcopy(plan)
        invalid["payload"]["phases"][0]["commit_mode"] = "eventually"
        # Recompute through create to prove rejection is semantic, not checksum-only.
        with self.assertRaisesRegex(CompilationError, "unsupported target"):
            AbmTickPlan.create(invalid["payload"])

    def test_dense_layout_identity_is_never_required_for_agents(self):
        spec = base_spec()
        spec["initial_state"]["agents"] = [
            {"id": "wolf-zeta", "kind": "wolf", "x": 0.0, "y": 0.0, "vars": {}},
            {"id": "wolf-alpha", "kind": "wolf", "x": 0.0, "y": 0.0, "vars": {}},
        ]

        plan = compile_model(spec).plan

        self.assertEqual([item["id"] for item in plan.payload["initial_state"]["agents"]],
                         ["wolf-zeta", "wolf-alpha"])

    def test_cross_backend_integer_range_is_rejected_before_plan_emission(self):
        spec = base_spec()
        spec["initial_state"]["globals"]["too_large"] = 2**63

        with self.assertRaisesRegex(CompilationError, "signed 64-bit"):
            compile_model(spec)


if __name__ == "__main__":
    unittest.main()
