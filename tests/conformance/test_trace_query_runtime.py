"""Runtime-backed acceptance for the bounded offline trace query contract."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from sim_engine_compiler.compiler import compile_aircraft_support
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.simpy_runtime import UnsupportedPlanError
from sim_engine_compiler.trace_query import query_trace

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC = ROOT / "tests" / "fixtures" / "synthetic"
F35 = ROOT / "tests" / "fixtures" / "spare_mvp" / "f35-43day-5352a0d"
LIMITATION = "unsigned_continuous_tail_deletion_undetectable"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(
    *,
    run_id: str,
    sample_index: int,
    seed: int,
    observation: str = "full",
    horizon: int | None = None,
    parameters: dict | None = None,
    backend: str = "python-reference",
) -> dict:
    value = {
        "run_id": run_id,
        "sample_index": sample_index,
        "seed": seed,
        "backend": backend,
        "observation": observation,
        "parameters": {} if parameters is None else parameters,
    }
    if horizon is not None:
        value["horizon"] = horizon
    return value


def _codes(report: dict) -> set[str]:
    return {item["code"] for item in report["diagnostics"]}


def _wide_query(**overrides) -> dict:
    value = {"limit": 1000, "max_event_bytes": 1_048_576}
    value.update(overrides)
    return value


class HandCalculableRuntimeQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.b1_plan_path = SYNTHETIC / "b1-execution-plan.json"
        cls.b1_result_path = SYNTHETIC / "b1-reference-result.json"
        cls.b3_plan_path = SYNTHETIC / "b3-upstream-transport-execution-plan.json"
        cls.b3_result_path = SYNTHETIC / "b3-upstream-transport-reference-result.json"
        cls.b1_plan = ExecutionPlan.from_dict(_load(cls.b1_plan_path))
        cls.b3_plan = ExecutionPlan.from_dict(_load(cls.b3_plan_path))
        cls.b1_result = SimpyReferenceRuntime(cls.b1_plan, seed=0).run()
        cls.b3_result = SimpyReferenceRuntime(cls.b3_plan, seed=0).run()
        if cls.b1_result != _load(cls.b1_result_path):
            raise AssertionError("actual B1 runtime result differs from its persisted fixture")
        if cls.b3_result != _load(cls.b3_result_path):
            raise AssertionError("actual B3 runtime result differs from its persisted fixture")

    def test_b1_real_result_query_preserves_runtime_facts_and_inputs(self) -> None:
        before_result = content_digest(self.b1_result)
        before_files = {
            path: _file_sha256(path)
            for path in (self.b1_plan_path, self.b1_result_path)
        }
        request = _request(
            run_id="b1-real-run",
            sample_index=0,
            seed=0,
            horizon=self.b1_plan.duration_minutes,
        )

        report = query_trace(
            self.b1_result,
            request,
            self.b1_plan,
            query=_wide_query(time_start=20, time_end=31),
        )

        self.assertEqual(report["status"], "partial")
        self.assertIn(LIMITATION, report["limitations"])
        self.assertTrue(report["events"])
        self.assertEqual(
            [event["recorded_sequence"] for event in report["events"]],
            sorted(event["recorded_sequence"] for event in report["events"]),
        )
        launch = next(
            event for event in report["events"] if event["kind"] == "mission_launched"
        )
        self.assertEqual(launch["recorded_references"]["entity"], "sortie-a-d1-w1")
        self.assertEqual(launch["facts"]["recorded"]["details"]["aircraft"], ["F35-01"])
        self.assertEqual(launch["trigger_relation"]["status"], "unknown")
        self.assertEqual(content_digest(self.b1_result), before_result)
        self.assertEqual(
            {path: _file_sha256(path) for path in before_files}, before_files
        )

    def test_b3_real_wait_process_is_recorded_without_inferred_wakeup_cause(self) -> None:
        complete = query_trace(
            self.b3_result,
            _request(
                run_id="b3-real-run",
                sample_index=0,
                seed=0,
                horizon=self.b3_plan.duration_minutes,
            ),
            self.b3_plan,
            query=_wide_query(process="job-0001"),
        )

        kinds = {event["kind"] for event in complete["events"]}
        self.assertTrue(
            {
                "spare_request",
                "spare_shortage",
                "organization_transport_arrived",
                "spare_consumed",
            }
            <= kinds
        )
        for event in complete["events"]:
            self.assertEqual(event["facts"]["process"]["reference"], "job-0001")
            self.assertEqual(event["trigger_relation"]["status"], "unknown")
            self.assertIn(
                "trigger_not_recorded",
                {gap["code"] for gap in event["facts"]["evidence_gaps"]},
            )

    def test_real_cancel_event_is_recorded_but_cancel_cause_remains_insufficient(self) -> None:
        inputs = _load(SYNTHETIC / "b1-daily-operations.json")
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
        inputs["support_network"] = copy.deepcopy(
            _load(SYNTHETIC / "b3-upstream-transport.json")["support_network"]
        )
        for node in inputs["support_network"]["nodes"]:
            node["personnel_capacity"] = 0
            node["equipment_capacity"] = 0
        for activity in inputs["support_activities"]["activities"]:
            activity["resource_id"] = "line"
        preflight = inputs["support_activities"]["activities"][0]
        preflight["jobs"][0]["durationMinutes"] = 10
        preflight["jobs"][0]["spare"] = "filter,1"
        plan = compile_aircraft_support(inputs)
        result = SimpyReferenceRuntime(plan, seed=0).run()

        report = query_trace(
            result,
            _request(
                run_id="cancel-real-run",
                sample_index=0,
                seed=0,
                horizon=plan.duration_minutes,
            ),
            plan,
            query=_wide_query(entity="cancelled-sortie-d1-w1"),
        )

        cancelled = [
            event for event in report["events"] if event["kind"] == "mission_cancelled"
        ]
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(cancelled[0]["time"], 4)
        self.assertEqual(cancelled[0]["facts"]["status"], "recorded")
        self.assertEqual(cancelled[0]["trigger_relation"]["status"], "unknown")
        self.assertIn(
            "guard_evaluation_not_recorded",
            {gap["code"] for gap in cancelled[0]["facts"]["evidence_gaps"]},
        )

    def test_persisted_result_and_raw_request_reload_without_mutation(self) -> None:
        request = _request(
            run_id="b3-persisted-run",
            sample_index=4,
            seed=0,
            horizon=self.b3_plan.duration_minutes,
            parameters={"case": "b3-upstream-transport"},
        )
        result_digest = content_digest(self.b3_result)
        request_digest = content_digest(request)
        with tempfile.TemporaryDirectory(prefix="trace-query-runtime-") as directory:
            result_path = Path(directory) / "result.json"
            request_path = Path(directory) / "request.json"
            result_path.write_text(json.dumps(self.b3_result, ensure_ascii=False))
            request_path.write_text(json.dumps(request, ensure_ascii=False))

            loaded_result = _load(result_path)
            loaded_request = _load(request_path)
            report = query_trace(
                loaded_result,
                loaded_request,
                self.b3_plan,
                query=_wide_query(process="job-0001"),
            )

            self.assertEqual(report["status"], "partial")
            self.assertTrue(report["events"])
            self.assertEqual(content_digest(loaded_result), result_digest)
            self.assertEqual(content_digest(loaded_request), request_digest)
            self.assertEqual(report["source_identity"]["result_digest"], result_digest)
            self.assertEqual(report["source_identity"]["request_digest"], request_digest)


class ReferenceCapabilityBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = ExecutionPlan.from_dict(_load(SYNTHETIC / "b1-execution-plan.json"))
        cls.result = SimpyReferenceRuntime(cls.plan, seed=0).run()

    def test_summary_request_does_not_reclassify_actual_full_result_as_summary(self) -> None:
        before = content_digest(self.result)

        report = query_trace(
            self.result,
            _request(
                run_id="summary-evidence-boundary",
                sample_index=0,
                seed=0,
                observation="summary",
                horizon=self.plan.duration_minutes,
            ),
            self.plan,
        )

        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["events"], [])
        self.assertEqual(report["coverage"]["level"], "none")
        self.assertEqual(
            report["coverage"]["source"]["reason"], "summary_observation"
        )
        self.assertIn("evidence_insufficient", _codes(report))
        self.assertEqual(content_digest(self.result), before)

    def test_python_reference_rejects_o5_profile_and_query_does_not_claim_it(self) -> None:
        raw = self.plan.to_dict()
        raw["semantic_profile"] = "event-time-v2"
        o5_plan = ExecutionPlan.from_dict(raw)

        with self.assertRaisesRegex(UnsupportedPlanError, "unsupported time profile"):
            SimpyReferenceRuntime(o5_plan, seed=0)

        report = query_trace(
            self.result,
            _request(
                run_id="unsupported-python-o5",
                sample_index=0,
                seed=0,
                horizon=o5_plan.duration_minutes,
            ),
            o5_plan,
        )
        self.assertIn(report["status"], {"unsupported", "invalid"})
        self.assertEqual(report["events"], [])
        self.assertNotIn("event-time-v2", report["support"]["profiles"])

    def test_rust_collection_request_is_explicitly_unsupported(self) -> None:
        report = query_trace(
            self.result,
            _request(
                run_id="rust-not-accepted",
                sample_index=0,
                seed=0,
                backend="rust-runtime",
            ),
            self.plan,
        )

        self.assertEqual(report["status"], "unsupported")
        self.assertEqual(report["events"], [])
        self.assertIn("unsupported_backend", _codes(report))


class F35FullRuntimeQueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan_path = F35 / "execution-plan.json"
        cls.inputs_path = F35 / "simulation-inputs.json"
        cls.manifest_path = F35 / "manifest.json"
        cls.source_hashes = {
            path: _file_sha256(path)
            for path in (cls.plan_path, cls.inputs_path, cls.manifest_path)
        }
        cls.plan = ExecutionPlan.from_dict(_load(cls.plan_path))
        cls.results = {
            seed: SimpyReferenceRuntime(cls.plan, seed=seed).run()
            for seed in (0, 1, 7)
        }

    def test_required_seeds_query_real_full_results_without_mutating_sources(self) -> None:
        event_ids: dict[int, str] = {}
        for sample_index, seed in enumerate((0, 1, 7)):
            with self.subTest(seed=seed):
                result = self.results[seed]
                before = content_digest(result)
                request = _request(
                    run_id="f35-python-full",
                    sample_index=sample_index,
                    seed=seed,
                    horizon=self.plan.duration_minutes,
                    parameters={"fixture": "f35-43day-5352a0d"},
                )
                report = query_trace(
                    result,
                    request,
                    self.plan,
                    query=_wide_query(time_start=0, time_end=301),
                )

                self.assertEqual(report["status"], "partial")
                self.assertTrue(report["events"])
                self.assertTrue(
                    all(0 <= event["time"] < 301 for event in report["events"])
                )
                self.assertEqual(content_digest(result), before)
                self.assertEqual(
                    report["run_identity"]["identity"]["sample_index"], sample_index
                )
                self.assertEqual(report["run_identity"]["request"]["seed"], seed)
                self.assertEqual(report["source_identity"]["result_digest"], before)
                event_ids[seed] = report["events"][0]["event_id"]

                summary = query_trace(
                    result,
                    _request(
                        run_id="f35-python-summary-boundary",
                        sample_index=sample_index,
                        seed=seed,
                        observation="summary",
                        horizon=self.plan.duration_minutes,
                        parameters={"fixture": "f35-43day-5352a0d"},
                    ),
                    self.plan,
                )
                self.assertEqual(summary["status"], "partial")
                self.assertEqual(summary["events"], [])
                self.assertEqual(summary["coverage"]["level"], "none")
                self.assertEqual(
                    summary["coverage"]["source"]["reason"],
                    "summary_observation",
                )
                self.assertEqual(content_digest(result), before)

        self.assertEqual(len(set(event_ids.values())), 3)
        self.assertEqual(
            {path: _file_sha256(path) for path in self.source_hashes},
            self.source_hashes,
        )


if __name__ == "__main__":
    unittest.main()
