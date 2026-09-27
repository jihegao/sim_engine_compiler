from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from sim_engine_compiler.identity.artifacts import inspect_bundle
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.identity.runs import (
    build_run_identity,
    inspect_run_identity,
    project_event_references,
    resolve_event_reference,
)
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime

ROOT = Path(__file__).resolve().parents[2]


class RunAndEventIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = ExecutionPlan.from_dict(
            json.loads(
                (ROOT / "tests/fixtures/identity_contract/b1/plan.json").read_text()
            )
        )
        cls.result = SimpyReferenceRuntime(cls.plan, seed=7).run()

    def _identity(self, **overrides):
        values = {"run_id": "run-a", "sample_index": 0, "seed": 7,
                  "plan": self.plan}
        values.update(overrides)
        return build_run_identity(**values)

    def test_repeated_seed_uses_run_and_sample_not_seed_as_identity(self):
        first = self._identity(sample_index=0)
        second = self._identity(sample_index=1)
        other_run = self._identity(run_id="run-b", sample_index=0)

        self.assertEqual(first["request"]["seed"], second["request"]["seed"])
        self.assertNotEqual(first["identity"]["sample_id"],
                            second["identity"]["sample_id"])
        self.assertNotEqual(first["identity"]["sample_id"],
                            other_run["identity"]["sample_id"])

    def test_request_rejects_bool_integer_and_nonfinite_parameter(self):
        self.assertEqual(self._identity(sample_index=True)["status"], "invalid")
        self.assertEqual(self._identity(seed=False)["status"], "invalid")
        report = self._identity(parameters={"threshold": float("nan")})
        self.assertEqual(report["status"], "invalid")
        self.assertEqual(report["diagnostics"][0]["code"], "invalid_parameters")

    def test_unknown_plan_schema_profile_and_abm_domain_are_unsupported(self):
        unknown_schema = json.loads(json.dumps(self.plan.to_dict()))
        unknown_schema["plan_version"] = "aircraft-support-plan/v99"
        unknown_profile = json.loads(json.dumps(self.plan.to_dict()))
        unknown_profile["semantic_profile"] = "future-time-v9"
        abm = {
            "plan_version": self.plan.plan_version,
            "domain": "abm-tick",
            "semantic_profile": "legacy-minute-v1",
            "rng_profile": "legacy-sequential-v1",
        }

        for value in (unknown_schema, unknown_profile, abm):
            with self.subTest(value=value):
                self.assertEqual(self._identity(plan=value)["status"], "unsupported")

    def test_inspection_detects_mutation_instead_of_trusting_status(self):
        identity = self._identity()
        identity["status"] = "invalid"

        inspected = inspect_run_identity(identity)

        self.assertEqual(inspected["status"], "invalid")
        self.assertEqual(inspected["diagnostics"][0]["code"],
                         "run_identity_digest_mismatch")

    def test_inspection_returns_structured_error_for_hostile_field_types(self):
        for path, value in (
            (("execution_contract", "semantic_profile"), ["legacy-minute-v1"]),
            (("bundle_binding", "status"), ["not_supplied"]),
        ):
            with self.subTest(path=path):
                identity = self._identity()
                identity[path[0]][path[1]] = value
                identity.pop("content_digest")
                identity["content_digest"] = content_digest(identity)

                inspected = inspect_run_identity(identity)

                self.assertIn(inspected["status"], {"invalid", "unsupported"})

    def test_raw_bundle_is_revalidated_but_a_prior_report_is_not_authority(self):
        fixture = ROOT / "tests/fixtures/identity_contract/b1"
        bundle = {
            name: json.loads((fixture / f"{name}.json").read_text())
            for name in ("business", "core", "plan", "lineage")
        }

        identity = self._identity(plan=bundle["plan"], bundle=bundle)
        inspected = inspect_run_identity(identity)
        untrusted_report = inspect_bundle(**bundle)
        rejected = self._identity(plan=bundle["plan"], bundle=untrusted_report)

        self.assertEqual(identity["bundle_binding"]["status"], "matched")
        self.assertEqual(inspected["status"], "partial")
        self.assertEqual(inspected["diagnostics"][0]["code"],
                         "bundle_revalidation_unavailable")
        self.assertEqual(rejected["status"], "invalid")

    def test_result_binding_rejects_wrong_plan_seed_sample_and_profile(self):
        identity = self._identity()
        cases = {
            "plan_fingerprint": "0" * 64,
            "seed": 8,
            "sample_index": 1,
            "semantic_profile": "event-time-v2",
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                result = copy.deepcopy(self.result)
                result[field] = value
                report = project_event_references(identity, result)
                self.assertEqual(report["status"], "invalid")
                self.assertIn("mismatch", report["diagnostics"][0]["code"])

    def test_filtered_projection_preserves_original_event_identity(self):
        identity = self._identity()
        complete = project_event_references(identity, self.result)
        target_sequence = complete["events"][4]["recorded_sequence"]
        target_id = complete["events"][4]["event_id"]

        filtered = project_event_references(
            identity, self.result, selected_sequences=[target_sequence]
        )

        self.assertEqual(filtered["events"][0]["event_id"], target_id)
        self.assertEqual(filtered["events"][0]["recorded_sequence"], target_sequence)
        self.assertEqual(filtered["events"][0]["trigger_relation"]["status"],
                         "unknown")
        self.assertEqual(filtered["events"][0]["trigger_relation"]["event_ids"], [])
        self.assertEqual(filtered["status"], "partial")
        self.assertEqual(filtered["coverage"]["level"], "partial")

    def test_event_from_another_run_does_not_resolve(self):
        first = project_event_references(self._identity(), self.result)
        second = project_event_references(self._identity(run_id="run-b"), self.result)

        resolution = resolve_event_reference(
            second, first["events"][0]["event_id"]
        )

        self.assertEqual(resolution["status"], "invalid")
        self.assertEqual(resolution["diagnostics"][0]["code"],
                         "cross_sample_event_reference")

    def test_filtered_target_reports_evidence_insufficient(self):
        identity = self._identity()
        complete = project_event_references(identity, self.result)
        retained = complete["events"][0]["recorded_sequence"]
        omitted_id = complete["events"][1]["event_id"]
        filtered = project_event_references(
            identity, self.result, selected_sequences=[retained]
        )

        resolution = resolve_event_reference(filtered, omitted_id)

        self.assertEqual(resolution["status"], "partial")
        self.assertEqual(resolution["reason"], "event_filtered")
        self.assertEqual(resolution["diagnostics"][0]["code"],
                         "evidence_insufficient")

    def test_summary_absent_trace_and_truncation_are_machine_readable(self):
        summary = project_event_references(
            self._identity(observation="summary"),
            {"plan_fingerprint": self.plan.fingerprint, "seed": 7},
        )
        absent = project_event_references(
            self._identity(),
            {"plan_fingerprint": self.plan.fingerprint, "seed": 7},
        )
        truncated = project_event_references(
            self._identity(), self.result, truncated=True
        )

        self.assertEqual(summary["coverage"]["reason"], "summary_observation")
        self.assertEqual(absent["coverage"]["reason"], "trace_not_captured")
        self.assertEqual(truncated["coverage"]["reason"], "trace_truncated")
        for report in (summary, absent, truncated):
            self.assertEqual(report["status"], "partial")
            self.assertEqual(report["diagnostics"][0]["code"],
                             "evidence_insufficient")

    def test_unparseable_or_duplicate_sequence_is_rejected(self):
        identity = self._identity()
        result = copy.deepcopy(self.result)
        result["trace"][0]["sequence"] = True
        self.assertEqual(project_event_references(identity, result)["status"],
                         "invalid")

        result = copy.deepcopy(self.result)
        result["trace"][1]["sequence"] = result["trace"][0]["sequence"]
        self.assertEqual(project_event_references(identity, result)["status"],
                         "invalid")

    def test_current_result_marks_only_fields_that_were_actually_verified(self):
        projection = project_event_references(self._identity(), self.result)

        self.assertEqual(projection["status"], "partial")
        self.assertEqual(projection["coverage"]["level"], "partial")
        self.assertEqual(projection["coverage"]["reason"],
                         "result_binding_incomplete")
        self.assertEqual(projection["evidence_binding"]["verified_result_fields"],
                         ["plan_fingerprint", "seed"])
        self.assertFalse(
            projection["evidence_binding"]["proves_runtime_consumed_plan"]
        )
        event = projection["events"][0]
        self.assertEqual(event["reference_scope"]["entity_role"], "unknown")
        self.assertEqual(event["reference_scope"]["core_plan_element"], "unknown")

    def test_explicit_result_binding_can_complete_reference_projection(self):
        result = copy.deepcopy(self.result)
        result["sample_index"] = 0
        result["semantic_profile"] = self.plan.semantic_profile

        projection = project_event_references(self._identity(), result)

        self.assertEqual(projection["status"], "valid")
        self.assertEqual(projection["coverage"]["level"], "complete")
        self.assertEqual(projection["coverage"]["reason"], "full_trace")
        self.assertFalse(
            projection["evidence_binding"]["proves_runtime_consumed_plan"]
        )

    def test_projection_run_identity_cannot_be_reassigned_and_rehashed(self):
        result = copy.deepcopy(self.result)
        result["sample_index"] = 0
        result["semantic_profile"] = self.plan.semantic_profile
        projection = project_event_references(self._identity(), result)
        projection["run_identity"]["run_id"] = "forged-run"
        projection.pop("content_digest")
        projection["content_digest"] = content_digest(projection)

        resolution = resolve_event_reference(
            projection, projection["events"][0]["event_id"]
        )

        self.assertEqual(resolution["status"], "invalid")
        self.assertEqual(resolution["diagnostics"][0]["code"],
                         "invalid_event_projection")


if __name__ == "__main__":
    unittest.main()
