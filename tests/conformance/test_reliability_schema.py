from __future__ import annotations

import copy
import tempfile
from pathlib import Path
import unittest

from sim_engine_compiler.diagnostics import CompilationError
from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.domains.aircraft_support.reliability import build_reliability_business
from sim_engine_compiler.domains.aircraft_support.lowering import lower_business
from sim_engine_compiler.integrations.spare_mvp.importer import import_business_ir
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.product import (
    compile_bundle,
    load_bundle,
    seal_business,
    validate_business,
)
from sim_engine_compiler.ir.reliability import (
    RELIABILITY_POLICY,
    ReliabilityComponentInstanceState,
    aircraft_healthy,
    complete_repair,
    group_healthy,
    repair_duration_minutes_for,
    runtime_instance_ids,
)


def inputs(components, *, aircraft_ids=("F35-01",)):
    return {
        "schema_version": "aircraft-support-v1-input-v1",
        "operations_support_policy": "daily-v1",
        "semantic_profile": "legacy-minute-v1",
        "equipment_tree": {"components": components},
        "aircraft": {
            "assets": [
                {"tail_number": value, "aircraft_type": "F35", "model": "F35"}
                for value in aircraft_ids
            ]
        },
        "time": {"duration_minutes": 1440, "tick_minutes": 1},
    }


def state(plan, aircraft_index, aircraft_id, template_id, **overrides):
    instance = next(
        item
        for item in plan.component_instances
        if item.instance_template_id == template_id
    )
    values = {
        "runtime_instance_id": f"{aircraft_id}/{template_id}",
        "aircraft_index": aircraft_index,
        "aircraft_id": aircraft_id,
        "instance_template_id": template_id,
        "group_index": instance.group_index,
        "parent_instance_index": instance.parent_instance_index
        if instance.parent_instance_index >= 0
        else None,
        "remaining_exposure": 10.0,
    }
    values.update(overrides)
    return ReliabilityComponentInstanceState(**values)


def states(plan, aircraft_index=0, aircraft_id="F35-01", overrides=None):
    overrides = overrides or {}
    return tuple(
        state(
            plan,
            aircraft_index,
            aircraft_id,
            instance.instance_template_id,
            **overrides.get(instance.instance_template_id, {}),
        )
        for instance in plan.component_instances
    )


class ReliabilitySchemaTests(unittest.TestCase):
    def test_different_component_groups_are_series(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {"id": "A", "component_type_id": "A", "quantity": 1, "failure_rate_per_hour": 0.5},
                    {"id": "B", "component_type_id": "B", "quantity": 1, "failure_rate_per_hour": 0.5},
                ]
            )
        )
        self.assertTrue(aircraft_healthy(plan, states(plan), 0))
        self.assertFalse(
            aircraft_healthy(
                plan,
                states(plan, overrides={"A-0": {"failed": True, "failed_at": 3}}),
                0,
            )
        )
        self.assertFalse(
            aircraft_healthy(
                plan,
                states(plan, overrides={"B-0": {"failed": True, "failed_at": 3}}),
                0,
            )
        )

    def test_quantity_two_without_redundancy_is_series(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                    }
                ]
            )
        )
        self.assertEqual(len(plan.component_instances), 2)
        values = states(plan, overrides={"A-0": {"failed": True, "failed_at": 2}})
        self.assertFalse(group_healthy(plan, values, 0, 0))
        self.assertFalse(aircraft_healthy(plan, values, 0))

    def test_k_out_of_n_keeps_group_healthy_with_one_instance(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                        "redundancy": {"kind": "k_out_of_n", "k": 1, "n": 2},
                    }
                ]
            )
        )
        one_failed = states(plan, overrides={"A-0": {"failed": True}})
        self.assertTrue(group_healthy(plan, one_failed, 0, 0))
        self.assertTrue(aircraft_healthy(plan, one_failed, 0))

        two_failed = states(
            plan,
            overrides={
                "A-0": {"failed": True},
                "A-1": {"failed": True},
            },
        )
        self.assertFalse(group_healthy(plan, two_failed, 0, 0))
        self.assertFalse(aircraft_healthy(plan, two_failed, 0))

    def test_legacy_k_out_of_n_alias_is_accepted_by_new_schema(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                        "k_out_of_n": {"enabled": True, "k": 1, "n": 2},
                    }
                ]
            )
        )
        self.assertEqual(plan.component_groups[0].redundancy_kind, "k_out_of_n")
        self.assertEqual(plan.component_groups[0].redundancy_k, 1)
        self.assertEqual(plan.component_groups[0].redundancy_n, 2)

    def test_same_component_type_in_different_positions_is_not_merged(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "left-A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_rate_per_hour": 0.5,
                    },
                    {
                        "id": "right-A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_rate_per_hour": 0.5,
                    },
                ]
            )
        )
        self.assertEqual([group.group_id for group in plan.component_groups], ["left-A", "right-A"])
        self.assertEqual({instance.group_index for instance in plan.component_instances}, {0, 1})

    def test_parent_instance_mapping_is_consistent_across_core_and_plan(self):
        source = inputs(
            [
                {"id": "P", "component_type_id": "P", "quantity": 2, "failure_rate_per_hour": 0.1},
                {
                    "id": "C",
                    "component_type_id": "C",
                    "quantity": 2,
                    "parent_id": "P",
                    "parent_instance_id": "P-0",
                    "failure_rate_per_hour": 0.2,
                },
                {
                    "id": "D",
                    "component_type_id": "D",
                    "quantity": 1,
                    "parent_id": "P",
                    "parent_instance_id": "P-1",
                    "failure_rate_per_hour": 0.3,
                },
            ]
        )
        core = lower_business(import_business_ir(source))
        core_by_id = {
            row["id"]: row for row in core.payload["tables"]["component_instances"]
        }
        self.assertEqual(core_by_id["C-0"]["references"]["parent_instance_index"], "P-0")
        self.assertEqual(core_by_id["C-1"]["references"]["parent_instance_index"], "P-0")
        self.assertEqual(core_by_id["D-0"]["references"]["parent_instance_index"], "P-1")

        plan = compile_aircraft_support(source)
        plan_by_id = {
            instance.instance_template_id: instance
            for instance in plan.component_instances
        }
        self.assertEqual(plan_by_id["C-0"].parent_instance_index, plan_by_id["P-0"].index)
        self.assertEqual(plan_by_id["C-1"].parent_instance_index, plan_by_id["P-0"].index)
        self.assertEqual(plan_by_id["D-0"].parent_instance_index, plan_by_id["P-1"].index)

        c_failed = states(plan, overrides={"C-0": {"failed": True}})
        self.assertFalse(group_healthy(plan, c_failed, 0, 1))
        self.assertFalse(aircraft_healthy(plan, c_failed, 0))

    def test_parent_instance_is_required_when_parent_has_multiple_instances(self):
        source = inputs(
            [
                {"id": "P", "component_type_id": "P", "quantity": 2, "failure_rate_per_hour": 0.1},
                {
                    "id": "C",
                    "component_type_id": "C",
                    "quantity": 1,
                    "parent_id": "P",
                    "failure_rate_per_hour": 0.2,
                },
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            build_reliability_business(source)
        self.assertEqual(raised.exception.code, "ambiguous_parent_instance")

    def test_mixed_parent_instances_are_rejected_by_plan_schema(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {"id": "P", "component_type_id": "P", "quantity": 2, "failure_rate_per_hour": 0.1},
                    {
                        "id": "C",
                        "component_type_id": "C",
                        "quantity": 2,
                        "parent_id": "P",
                        "parent_instance_id": "P-0",
                        "failure_rate_per_hour": 0.2,
                    },
                ]
            )
        )
        raw = plan.to_dict()
        raw["component_instances"][3]["parent_instance_index"] = 2
        with self.assertRaises(CompilationError) as raised:
            ExecutionPlan.from_dict(copy.deepcopy(raw))
        self.assertEqual(raised.exception.code, "mixed_parent_instance_unsupported")

    def test_new_plan_rejects_failure_threshold(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_rate_per_hour": 0.5,
                    }
                ]
            )
        )
        raw = plan.to_dict()
        raw["component_groups"][0]["failure_threshold"] = 2
        with self.assertRaises(CompilationError) as raised:
            ExecutionPlan.from_dict(copy.deepcopy(raw))
        self.assertEqual(raised.exception.code, "failure_threshold_in_new_plan")

        source = inputs(
            [
                {
                    "id": "A",
                    "component_type_id": "A",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.5,
                    "failure_threshold": 2,
                }
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            build_reliability_business(source)
        self.assertEqual(raised.exception.code, "failure_threshold_in_new_plan")

    def test_legacy_input_rejects_failure_threshold(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.5,
                    "failure_threshold": 2,
                }
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            compile_aircraft_support(source)
        self.assertEqual(raised.exception.code, "failure_threshold_in_new_plan")
        self.assertEqual(
            raised.exception.source_path,
            "equipment_tree.components[0].failure_threshold",
        )

    def test_nested_instance_failure_threshold_is_rejected(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "component_type_id": "A",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.5,
                    "instances": [
                        {"instance_id": "A-0", "failure_threshold": 2},
                    ],
                }
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            compile_aircraft_support(source)
        self.assertEqual(raised.exception.code, "failure_threshold_in_new_plan")
        self.assertEqual(
            raised.exception.source_path,
            "equipment_tree.components[0].instances[0].failure_threshold",
        )

    def test_mixed_reliability_and_legacy_components_are_rejected(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "component_type_id": "A",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.5,
                },
                {
                    "id": "B",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.5,
                },
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            compile_aircraft_support(source)
        self.assertEqual(raised.exception.code, "component_type_missing")
        self.assertEqual(
            raised.exception.source_path,
            "equipment_tree.components[1].component_type_id",
        )

    def test_repair_only_restores_target_instance_and_reaggregates(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                        "redundancy": {"kind": "k_out_of_n", "k": 1, "n": 2},
                    }
                ]
            )
        )
        failed = states(
            plan,
            overrides={
                "A-0": {"failed": True, "failed_at": 1, "repairing": True},
                "A-1": {"failed": True, "failed_at": 1},
            },
        )
        self.assertFalse(group_healthy(plan, failed, 0, 0))

        repaired = complete_repair(plan, failed, "F35-01/A-0")
        by_id = {item.instance_template_id: item for item in repaired}
        self.assertFalse(by_id["A-0"].failed)
        self.assertFalse(by_id["A-0"].repairing)
        self.assertTrue(by_id["A-1"].failed)
        self.assertTrue(group_healthy(plan, repaired, 0, 0))
        self.assertTrue(aircraft_healthy(plan, repaired, 0))

    def test_repair_does_not_restore_series_group_while_other_instance_failed(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                    }
                ]
            )
        )
        failed = states(
            plan,
            overrides={
                "A-0": {"failed": True, "failed_at": 1},
                "A-1": {"failed": True, "failed_at": 1},
            },
        )
        repaired = complete_repair(plan, failed, "F35-01/A-0")
        self.assertFalse(group_healthy(plan, repaired, 0, 0))
        self.assertFalse(aircraft_healthy(plan, repaired, 0))

    def test_plan_template_can_materialize_runtime_identities_for_each_aircraft(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_rate_per_hour": 0.5,
                    }
                ],
                aircraft_ids=("F35-01", "F35-02"),
            )
        )
        self.assertEqual(len(plan.component_instances), 1)
        self.assertEqual(
            runtime_instance_ids(plan, "F35-01", 0), ("F35-01/A-0",)
        )
        self.assertEqual(
            runtime_instance_ids(plan, "F35-02", 1), ("F35-02/A-0",)
        )

    def test_failure_rate_defaults_and_instance_overrides(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                        "instances": [
                            {"instance_id": "A-0"},
                            {"instance_id": "A-1", "failure_rate_per_hour": 0.25},
                        ],
                    }
                ]
            )
        )
        by_id = {
            instance.instance_template_id: instance
            for instance in plan.component_instances
        }
        self.assertEqual(by_id["A-0"].failure_rate_per_hour, 0.5)
        self.assertEqual(by_id["A-1"].failure_rate_per_hour, 0.25)

    def test_missing_failure_rate_defaults_to_zero(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "component_type_id": "A",
                    "quantity": 2,
                    "instances": [
                        {"instance_id": "A-0"},
                        {"instance_id": "A-1"},
                    ],
                }
            ]
        )
        plan = compile_aircraft_support(source)
        self.assertEqual(
            [item.failure_rate_per_hour for item in plan.component_instances],
            [0.0, 0.0],
        )

    def test_mtbf_distribution_is_converted_to_instance_rate(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_distribution": {
                            "distributionType": "exponential",
                            "mtbf": 50,
                            "timeUnit": "hour",
                            "timeBasis": "flight_hour",
                        },
                    }
                ]
            )
        )
        self.assertEqual(plan.component_instances[0].failure_rate_per_hour, 0.02)

    def test_explicit_zero_failure_rate_is_valid(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_rate_per_hour": 0,
                    }
                ]
            )
        )
        self.assertEqual(plan.component_instances[0].failure_rate_per_hour, 0.0)

    def test_repair_duration_priority_is_instance_then_group_then_fallback(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 3,
                        "failure_rate_per_hour": 0.5,
                        "repair_profile": {"repairTimeMinutes": 30},
                        "instances": [
                            {"instance_id": "A-0"},
                            {
                                "instance_id": "A-1",
                                "repair_profile": {"repairTimeMinutes": 45},
                            },
                            {
                                "instance_id": "A-2",
                                "repair_profile": {"repairTimeMinutes": 0},
                            },
                        ],
                    }
                ]
            )
        )
        by_id = {
            instance.instance_template_id: instance.index
            for instance in plan.component_instances
        }
        self.assertEqual(repair_duration_minutes_for(plan, 0, by_id["A-0"]), 30)
        self.assertEqual(repair_duration_minutes_for(plan, 0, by_id["A-1"]), 45)
        self.assertEqual(repair_duration_minutes_for(plan, 0, by_id["A-2"]), 0)

    def test_historical_v1alpha2_plan_still_loads_as_legacy(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "synthetic"
            / "b2-failure-repair-execution-plan.json"
        )
        import json

        raw = json.loads(path.read_text(encoding="utf-8"))
        plan = ExecutionPlan.from_dict(raw)
        self.assertEqual(plan.plan_version, "aircraft-support-plan/v1alpha2")
        self.assertIsNone(plan.reliability_policy)
        self.assertEqual(plan.component_groups, ())
        self.assertEqual(plan.component_instances, ())
        self.assertTrue(plan.components)
        self.assertIn("failure_threshold", raw["components"][0])

    def test_seal_and_compile_preserve_reliability_fingerprints(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "component_type_id": "A",
                    "quantity": 2,
                    "failure_rate_per_hour": 0.5,
                    "redundancy": {"kind": "k_out_of_n", "k": 1, "n": 2},
                },
                {
                    "id": "B",
                    "component_type_id": "B",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.1,
                },
            ]
        )
        sealed = seal_business(import_business_ir(source).payload)
        first = validate_business(sealed)
        second = validate_business(sealed)
        self.assertEqual(first["status"], "valid")
        self.assertEqual(first["identity"], second["identity"])

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "reliability.simpack"
            compiled = compile_bundle(sealed, target)
            self.assertEqual(compiled["status"], "valid")
            bundle = load_bundle(target)
            self.assertEqual(bundle.manifest["ir_versions"]["plan"],
                             "aircraft-support-plan/v1alpha2")
            self.assertEqual(
                bundle.manifest["identity"]["plan_fingerprint"],
                first["identity"]["plan_fingerprint"],
            )

    def test_plan_json_roundtrips_without_failure_threshold(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 2,
                        "failure_rate_per_hour": 0.5,
                        "redundancy": {"kind": "k_out_of_n", "k": 1, "n": 2},
                    }
                ]
            )
        )
        raw = plan.to_dict()
        self.assertNotIn("failure_threshold", repr(raw))
        self.assertEqual(ExecutionPlan.from_dict(raw), plan)

    def test_quantity_and_explicit_instances_must_match(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "component_type_id": "A",
                    "quantity": 2,
                    "failure_rate_per_hour": 0.5,
                    "instances": [{"instance_id": "A-0"}],
                }
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            build_reliability_business(source)
        self.assertEqual(raised.exception.code, "quantity_instance_mismatch")

    def test_component_type_is_required(self):
        source = inputs(
            [
                {
                    "id": "A",
                    "quantity": 1,
                    "failure_rate_per_hour": 0.5,
                }
            ]
        )
        with self.assertRaises(CompilationError) as raised:
            build_reliability_business(source)
        self.assertEqual(raised.exception.code, "component_type_missing")

    def test_python_rust_shared_fused_reliability_fixture(self):
        import json

        fixture = (
            Path(__file__).resolve().parents[1]
            / "fixtures"
            / "reliability"
        )
        source = json.loads((fixture / "r1-fused-input.json").read_text(encoding="utf-8"))
        expected = json.loads(
            (fixture / "r1-fused-input-plan.json").read_text(encoding="utf-8")
        )
        plan = compile_aircraft_support(source)
        self.assertEqual(json.loads(json.dumps(plan.to_dict())), expected)
        self.assertEqual(plan.reliability_policy, RELIABILITY_POLICY)
        self.assertEqual(plan.component_groups[1].parent_group_index, 0)
        self.assertEqual(
            [item.failure_rate_per_hour for item in plan.component_instances],
            [0.0, 0.5, 0.25],
        )

    def test_semantic_profile_and_reliability_policy_are_separate(self):
        plan = compile_aircraft_support(
            inputs(
                [
                    {
                        "id": "A",
                        "component_type_id": "A",
                        "quantity": 1,
                        "failure_rate_per_hour": 0.5,
                    }
                ]
            )
        )
        self.assertEqual(plan.semantic_profile, "legacy-minute-v1")
        self.assertEqual(plan.reliability_policy, RELIABILITY_POLICY)

        raw = plan.to_dict()
        raw["semantic_profile"] = "event-time-v2"
        reloaded = ExecutionPlan.from_dict(copy.deepcopy(raw))
        self.assertEqual(reloaded.semantic_profile, "event-time-v2")
        self.assertEqual(reloaded.reliability_policy, RELIABILITY_POLICY)

        del raw["reliability_policy"]
        with self.assertRaises(CompilationError) as raised:
            ExecutionPlan.from_dict(copy.deepcopy(raw))
        self.assertEqual(raised.exception.code, "unsupported_reliability_policy")


if __name__ == "__main__":
    unittest.main()
