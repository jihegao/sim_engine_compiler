from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "benchmarks/mlir_resource_dispatch/results/f35-20260924-v1"
BASELINE_PLAN = EVIDENCE / "baseline-plan.json"
MLIR_PLAN = EVIDENCE / "mlir-pass-on-plan.json"
REPORT = EVIDENCE / "evidence.json"


def _cargo() -> str:
    found = shutil.which("cargo")
    if found:
        return found
    fallback = Path.home() / ".cargo/bin/cargo"
    if fallback.is_file():
        return str(fallback)
    raise AssertionError("Rust conformance requires cargo")


def _rechecksum(index: dict) -> None:
    index.pop("checksum", None)
    encoded = json.dumps(
        index, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    index["checksum"] = hashlib.sha256(encoded).hexdigest()


class MlirResourceDispatchPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not MLIR_PLAN.is_file() or not BASELINE_PLAN.is_file() or not REPORT.is_file():
            raise unittest.SkipTest("run scripts/benchmark_mlir_resource_dispatch.py first")
        subprocess.run(
            [
                _cargo(),
                "build",
                "--quiet",
                "--locked",
                "--release",
                "--bin",
                "sim-engine-runtime",
                "--manifest-path",
                str(ROOT / "rust/runtime/Cargo.toml"),
            ],
            cwd=ROOT,
            check=True,
        )
        cls.binary = ROOT / "rust/runtime/target/release/sim-engine-runtime"
        cls.plan_raw = json.loads(MLIR_PLAN.read_text(encoding="utf-8"))
        cls.plan = ExecutionPlan.from_dict(cls.plan_raw)
        cls.tempdir = tempfile.TemporaryDirectory(prefix="sim-mlir-pilot-tests-")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "tempdir"):
            cls.tempdir.cleanup()

    def run_rust(self, plan_path: Path, seed: int, *, until: int | None = None):
        output = Path(self.tempdir.name) / f"{plan_path.stem}-{seed}-{until}.json"
        command = [str(self.binary), str(plan_path), str(output), "--seed", str(seed)]
        if until is not None:
            command.extend(("--until", str(until)))
        completed = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True
        )
        return completed, output

    def test_mlir_index_is_attached_deterministically_to_the_base_plan(self):
        evidence = json.loads(REPORT.read_text(encoding="utf-8"))
        index = self.plan_raw["resource_dispatch_index"]
        checksums = {
            item["resource_dispatch_index_checksum"]
            for item in evidence["compile"]["mlir_on"]["compiler_metadata_samples"]
        }
        self.assertEqual(len(checksums), 1)
        self.assertEqual(index["checksum"], next(iter(checksums)))
        self.assertEqual(index["schema_version"], "resource-dispatch-index/v1")
        self.assertEqual(index["pass_name"], "sim-build-resource-dependency-index")
        self.assertEqual(evidence["semantic_plan_fingerprint"], self.plan.fingerprint)
        self.assertEqual(evidence["candidate_rule_count"], 852)
        dependency_keys = {
            (
                item["key"]["kind"],
                item["key"]["node_index"],
                item["key"].get("product_id"),
            )
            for item in index["dependencies"]
        }
        self.assertIn(("personnel_capacity", 1, None), dependency_keys)
        self.assertIn(("equipment_capacity", 1, None), dependency_keys)
        source_node = self.plan.supply_routes[0].source_node_index
        dynamic_products = {
            candidate["product_filter"]
            for item in index["dependencies"]
            for candidate in item["candidates"]
            if "product_filter" in candidate
        }
        self.assertTrue(dynamic_products)
        for product_id in dynamic_products:
            self.assertIn(("inventory", source_node, product_id), dependency_keys)

    def test_indexed_f35_full_results_match_the_python_reference(self):
        for seed in (0, 1, 7):
            with self.subTest(seed=seed):
                expected = SimpyReferenceRuntime(self.plan, seed=seed).run()
                completed, output = self.run_rust(MLIR_PLAN, seed)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                actual = json.loads(output.read_text(encoding="utf-8"))
                self.assertIsNone(
                    first_divergence(
                        expected,
                        actual,
                        float_rel_tol=2e-15,
                        float_abs_tol=1e-12,
                    )
                )

    def test_runtime_rejects_an_incomplete_index_even_with_a_valid_checksum(self):
        altered = json.loads(json.dumps(self.plan_raw))
        index = altered["resource_dispatch_index"]
        dependency = index["dependencies"][0]
        dependency["candidates"].pop()
        index["candidate_rule_count"] -= 1
        if not dependency["candidates"]:
            index["dependencies"].pop(0)
        _rechecksum(index)
        invalid_path = Path(self.tempdir.name) / "incomplete-index-plan.json"
        invalid_path.write_text(json.dumps(altered), encoding="utf-8")
        completed, _ = self.run_rust(invalid_path, 0, until=1)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("omits a required candidate rule", completed.stderr)

    def test_f35_profile_shows_guard_reduction_with_exact_three_arm_parity(self):
        evidence = json.loads(REPORT.read_text(encoding="utf-8"))
        runtime = evidence["runtime"]
        self.assertTrue(runtime["exact_full_result_parity"])
        records = runtime["records"]
        baseline_guards = sum(
            item["resource_dispatch_guard_evaluations"]
            for item in records
            if item["arm"] == "existing_compile_chain"
        )
        indexed_guards = sum(
            item["resource_dispatch_guard_evaluations"]
            for item in records
            if item["arm"] == "mlir_business_pass_enabled"
        )
        cache_hits = sum(
            item["resource_dispatch_cache_hits"]
            for item in records
            if item["arm"] == "mlir_business_pass_enabled"
        )
        self.assertLess(indexed_guards, baseline_guards)
        self.assertGreater(cache_hits, 0)


if __name__ == "__main__":
    unittest.main()
