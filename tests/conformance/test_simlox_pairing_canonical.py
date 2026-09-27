from __future__ import annotations

import unittest

from experiments.simlox_pairing.canonical import (
    HANDOFF_COMMIT,
    NATIVE_INPUT_SHA256,
    UPSTREAM_ADAPTER_REVISION,
    UPSTREAM_INPUT_SCHEMA_SHA256,
    build_canonical,
    compile_case,
)
from sim_engine_compiler.reference import SimpyReferenceRuntime


def _timeline(result: dict, kinds: set[str]) -> list[tuple[int, str, str]]:
    return [
        (event["time"], event["kind"], event["entity"])
        for event in result["trace"]
        if event["kind"] in kinds
    ]


class SimloxPairingCanonicalTests(unittest.TestCase):
    def test_build_canonical_rejects_an_unregistered_case(self):
        with self.assertRaisesRegex(ValueError, "expected A01 or A02"):
            build_canonical("A03")

    def test_canonical_identity_does_not_claim_project_translation(self):
        canonical = build_canonical("a01")
        self.assertEqual(
            canonical["project_identity"],
            {
                "project_id": "simlox-a01-pairing-teaching-input",
                "project_version": "1",
                "scenario_id": "A01",
                "source_import_id": "self-authored-pairing-input",
            },
        )
        self.assertEqual(canonical["schema_version"], "aircraft-support-v1-input-v1")
        self.assertEqual(canonical["time"]["duration_minutes"], 36 * 60)

    def test_compile_case_traverses_all_layers_and_is_deterministic(self):
        first = compile_case("A01")
        second = compile_case("A01")
        self.assertEqual(first.business.fingerprint, second.business.fingerprint)
        self.assertEqual(first.core.fingerprint, second.core.fingerprint)
        self.assertEqual(first.plan.fingerprint, second.plan.fingerprint)
        self.assertEqual(
            first.plan.source_inputs_sha256,
            first.business.payload["source"]["canonical_sha256"],
        )
        self.assertEqual(first.plan.unsupported_features, ())
        self.assertEqual(
            first.lineage["business_fingerprint"], first.business.fingerprint
        )
        self.assertEqual(first.lineage["core_fingerprint"], first.core.fingerprint)
        self.assertEqual(first.lineage["plan_fingerprint"], first.plan.fingerprint)

    def test_a01_plan_has_explicit_notice_launch_and_return_times(self):
        artifacts = compile_case("A01")
        mission = artifacts.plan.missions[0]
        self.assertEqual(
            (
                mission.preparation_start,
                mission.planned_start,
                mission.duration_minutes,
            ),
            (7 * 60, 8 * 60, 2 * 60),
        )
        self.assertEqual(
            _timeline(
                artifacts.result,
                {"preflight_created", "mission_launched", "mission_returned"},
            ),
            [
                (7 * 60, "preflight_created", "a01-mission-01-d1-w1"),
                (8 * 60, "mission_launched", "a01-mission-01-d1-w1"),
                (10 * 60, "mission_returned", "TEACH-AIR-01"),
            ],
        )

    def test_a02_plan_has_three_notice_launch_return_triplets(self):
        artifacts = compile_case("A02")
        self.assertEqual(
            [
                (
                    mission.preparation_start,
                    mission.planned_start,
                    mission.duration_minutes,
                )
                for mission in artifacts.plan.missions
            ],
            [
                (7 * 60, 8 * 60, 2 * 60),
                (19 * 60, 20 * 60, 2 * 60),
                (31 * 60, 32 * 60, 2 * 60),
            ],
        )
        self.assertEqual(
            [
                (event["time"], event["kind"])
                for event in artifacts.result["trace"]
                if event["kind"]
                in {"preflight_created", "mission_launched", "mission_returned"}
            ],
            [
                (7 * 60, "preflight_created"),
                (8 * 60, "mission_launched"),
                (10 * 60, "mission_returned"),
                (19 * 60, "preflight_created"),
                (20 * 60, "mission_launched"),
                (22 * 60, "mission_returned"),
                (31 * 60, "preflight_created"),
                (32 * 60, "mission_launched"),
                (34 * 60, "mission_returned"),
            ],
        )
        self.assertEqual(artifacts.result["metrics"]["planned_mission_waves"], 3)
        self.assertEqual(artifacts.result["metrics"]["completed_sorties"], 3)
        self.assertEqual(artifacts.result["metrics"]["elapsed_minutes"], 36 * 60)

    def test_notice_bookkeeping_holds_aircraft_non_available_without_work(self):
        artifacts = compile_case("A02")
        self.assertTrue(
            all(not activity.steps for activity in artifacts.plan.activities)
        )
        snapshots: list[tuple[int, str, str | None, tuple[int, ...]]] = []

        class BindingSnapshotRuntime(SimpyReferenceRuntime):
            def _emit(self, kind, rule_id, entity, details=None, source_path=None):
                super()._emit(kind, rule_id, entity, details, source_path)
                if kind == "preflight_created":
                    aircraft = self.aircraft[0]
                    snapshots.append(
                        (
                            self.minute,
                            aircraft.state,
                            self._mission_id(aircraft.current_mission_index),
                            tuple(sorted(aircraft.prepared_mission_indexes)),
                        )
                    )

        BindingSnapshotRuntime(artifacts.plan, seed=0).run()
        self.assertEqual(
            snapshots,
            [
                (7 * 60, "mission_ready", "a02-mission-01-d1-w1", (0,)),
                (19 * 60, "mission_ready", "a02-mission-02-d1-w1", (1,)),
                (31 * 60, "mission_ready", "a02-mission-03-d2-w1", (2,)),
            ],
        )

    def test_source_mapping_uses_stable_ids_and_declares_scope(self):
        artifacts = compile_case("A02")
        mapping = artifacts.source_mapping
        self.assertEqual(
            mapping["source_contract"],
            {
                "upstream_revision": UPSTREAM_ADAPTER_REVISION,
                "canonical_schema": "contracts/aircraft_support_v1_input.schema.json",
                "canonical_schema_sha256": UPSTREAM_INPUT_SCHEMA_SHA256,
                "native_handoff_commit": HANDOFF_COMMIT,
                "native_input_sha256": NATIVE_INPUT_SHA256["A02"],
                "input_classification": "self-authored canonical teaching input",
            },
        )
        self.assertEqual(
            mapping["aircraft"],
            {
                "native_instance": "<TEACH-AIR-01,0>",
                "canonical_tail_number": "TEACH-AIR-01",
                "engine_aircraft_index": 0,
                "source_path": "aircraft.assets[0]",
            },
        )
        self.assertEqual(
            [row["native_mission_instance"] for row in mapping["missions"]],
            [
                "<BASIC-MISSION,TEACH-UNIT,0,0,0>",
                "<BASIC-MISSION,TEACH-UNIT,0,0,1>",
                "<BASIC-MISSION,TEACH-UNIT,0,0,2>",
            ],
        )
        self.assertIn(
            "not modeled preparation work", mapping["notice_binding"]["semantic_scope"]
        )
        self.assertIn(
            "not inventory spare reservation",
            mapping["notice_binding"]["semantic_scope"],
        )
        self.assertEqual(
            [row["native_concept"] for row in mapping["event_mapping"]],
            [
                "notification",
                "allocation",
                "ready_for_assigned_mission",
                "start",
                "completion",
            ],
        )
        self.assertTrue(mapping["event_mapping"][0]["not_independent_event"])
        self.assertEqual(
            mapping["native_only_boundaries"],
            [
                "inner task interval 8.5h-9.5h",
                "zero-time native preparation log records",
            ],
        )


if __name__ == "__main__":
    unittest.main()
