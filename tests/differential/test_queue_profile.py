"""Python/Rust agreement for the restricted two-server queue profile."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from sim_engine_compiler.domains.multi_server_queue.model import (
    EXAMPLE_INPUT,
    import_canonical,
    lower,
)
from sim_engine_compiler.domains.multi_server_queue.runtime import execute
from sim_engine_compiler.native import native_available, run_plan
from sim_engine_compiler.trace_query import query_trace


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MANIFEST = ROOT / "rust" / "runtime" / "Cargo.toml"
BINARY = ROOT / "rust" / "runtime" / "target" / "release" / "sim-engine-runtime"
B1 = ROOT / "tests" / "fixtures" / "identity_contract" / "b1"
SEEDS = (0, 1, 7)

SECOND_INPUT = {
    "schema_version": "multi-server-queue-v1-input-v1",
    "profile": "multi-server-queue-v1",
    "horizon": {"minutes": 30},
    "arrivals": {
        "process": "poisson",
        "rate_per_minute": 0.1,
        "classes": [
            {"id": "alpha", "priority": 1, "weight": 1},
            {"id": "bravo", "priority": 5, "weight": 2},
        ],
    },
    "servers": [
        {"id": "left", "service_rate_per_minute": 1.0},
        {"id": "right", "service_rate_per_minute": 0.2},
    ],
    "priority_rule": {
        "id": "priority-rule",
        "discipline": "nonpreemptive-priority",
        "ordering": ["priority_descending", "arrival_time", "customer_id"],
        "server_choice": "lowest_index_idle",
    },
    "metrics": {"names": ["mean_wait"]},
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class QueueProfileDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not BINARY.is_file():
            subprocess.run(
                [
                    "cargo",
                    "+1.90.0",
                    "build",
                    "--locked",
                    "--release",
                    "--manifest-path",
                    str(RUNTIME_MANIFEST),
                    "--bin",
                    "sim-engine-runtime",
                ],
                cwd=ROOT,
                check=True,
            )
        if not native_available():
            raise AssertionError(
                "Rust binding is required; rebuild it with maturin so "
                "sim_engine_compiler._runtime imports"
            )

    def _rust(self, plan: dict, seed: int) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "plan.json"
            out = Path(tmp) / "out.json"
            plan_path.write_text(
                json.dumps(plan, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [str(BINARY), str(plan_path), str(out), "--seed", str(seed)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(out.read_text())

    def _assert_configuration(self, canonical: dict):
        business = import_canonical(canonical)
        _core, plan, _lineage = lower(business)
        self.assertEqual(len(plan["servers"]), 2)
        self.assertEqual(
            [item["operation"] for item in plan["operations"]],
            [
                "queue.poisson_arrival/v1",
                "queue.nonpreemptive_priority_seize/v1",
                "queue.exponential_service/v1",
                "queue.mean_wait/v1",
            ],
        )
        for seed in SEEDS:
            python = execute(plan, seed=seed, sample_index=0)
            rust = self._rust(plan, seed)
            bound = run_plan(plan, seed=seed)
            self.assertGreater(len(python["sample_requests"]), 1)
            self.assertEqual(python["sample_requests"][0]["purpose"], "interarrival")
            self.assertGreater(python["sample_requests"][0]["value_minutes"], 0.0)
            self.assertEqual(python, rust)
            self.assertEqual(python, bound)
            self.assertGreater(python["metrics"]["arrival_count"], 0)

    def test_two_compositions_agree_on_seeds_0_1_and_7(self):
        self._assert_configuration(EXAMPLE_INPUT)
        self._assert_configuration(SECOND_INPUT)
        example_plan = lower(import_canonical(EXAMPLE_INPUT))[1]
        second_plan = lower(import_canonical(SECOND_INPUT))[1]
        self.assertNotEqual(example_plan["arrival_rate_per_minute"], second_plan["arrival_rate_per_minute"])
        self.assertNotEqual(example_plan["horizon_minutes"], second_plan["horizon_minutes"])
        self.assertNotEqual(
            [item["id"] for item in example_plan["classes"]],
            [item["id"] for item in second_plan["classes"]],
        )

    def test_rust_queue_result_is_traceable_through_business_core_and_plan(self):
        business = import_canonical(EXAMPLE_INPUT)
        core, plan, lineage = lower(business)
        rust = self._rust(plan, 0)
        bundle = {
            "business": business.to_dict(),
            "core": core,
            "plan": plan,
            "lineage": lineage,
        }
        report = query_trace(
            rust,
            {
                "run_id": "queue-rust-0",
                "sample_index": 0,
                "seed": 0,
                "backend": "rust-runtime",
            },
            plan,
            bundle=bundle,
        )
        self.assertEqual(report["status"], "partial")
        self.assertNotIn("unsupported", {item["code"] for item in report["diagnostics"]})
        self.assertTrue(report["events"])
        self.assertEqual(report["events"][0]["facts"]["design_links"]["status"], "verified")
        self.assertTrue(report["events"][0]["facts"]["design_links"]["links"])
        self.assertEqual(report["evidence_binding"]["backend"], "rust-runtime")
        self.assertTrue(
            {"seed", "sample_index", "semantic_profile"}
            <= set(report["evidence_binding"]["verified_result_fields"])
        )
        for field, wrong_value in (("seed", 7), ("sample_index", 99)):
            with self.subTest(field=field):
                request = {
                    "run_id": "queue-rust-0",
                    "sample_index": 0,
                    "seed": 0,
                    "backend": "rust-runtime",
                }
                request[field] = wrong_value
                mismatched = query_trace(rust, request, plan, bundle=bundle)
                self.assertEqual(mismatched["status"], "invalid")
                self.assertEqual(mismatched["events"], [])
                self.assertEqual(mismatched["diagnostics"][0]["path"], f"result.{field}")
        filtered = query_trace(
            rust,
            {
                "run_id": "queue-rust-0",
                "sample_index": 0,
                "seed": 0,
                "backend": "rust-runtime",
            },
            plan,
            bundle=bundle,
            query={"entity": "customer-does-not-exist"},
        )
        self.assertEqual(filtered["events"], [])
        self.assertGreater(filtered["coverage"]["omitted_by_filter"], 0)

    def test_rust_aircraft_result_is_traceable(self):
        plan = json.loads((B1 / "plan.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b1.json"
            completed = subprocess.run(
                [str(BINARY), str(B1 / "plan.json"), str(out), "--seed", "0"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            rust = json.loads(out.read_text())
        bundle = {
            layer: json.loads((B1 / f"{layer}.json").read_text())
            for layer in ("business", "core", "plan", "lineage")
        }
        report = query_trace(
            rust,
            {
                "run_id": "b1-rust-0",
                "sample_index": 0,
                "seed": 0,
                "backend": "rust-runtime",
                "horizon": plan["duration_minutes"],
            },
            plan,
            bundle=bundle,
            query={"limit": 1000, "max_event_bytes": 1_048_576},
        )
        self.assertEqual(report["status"], "partial")
        self.assertNotIn("unsupported_backend", {item["code"] for item in report["diagnostics"]})
        self.assertTrue(report["events"])
        self.assertEqual(report["run_identity"]["status"], "partial")
        self.assertTrue(report["review_identity"])


class QueueBatchByteIdentityTests(unittest.TestCase):
    def test_fixed_run_id_batches_are_byte_identical(self):
        if not native_available():
            raise AssertionError("Rust binding is required for product batch")
        from sim_engine_compiler.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(main(["example", str(root), "--profile", "multi-server-queue-v1"]), 0)
            outputs = []
            for name in ("first.json", "second.json"):
                code = main([
                    "batch",
                    str(root / "baseline.simpack"),
                    "--seeds",
                    "0,1,7",
                    "--run-id",
                    "queue-batch-fixed",
                    "--output",
                    str(root / name),
                ])
                self.assertEqual(code, 0)
                outputs.append(root / name)
            self.assertEqual(outputs[0].read_bytes(), outputs[1].read_bytes())
            self.assertEqual(_sha256(outputs[0]), _sha256(outputs[1]))
            decoded = json.loads(outputs[0].read_text())
            self.assertEqual(
                [sample["seed"] for sample in decoded["result"]["samples"]],
                [0, 1, 7],
            )
            self.assertGreater(len(decoded["result"]["samples"][0]["result"]["sample_requests"]), 1)
