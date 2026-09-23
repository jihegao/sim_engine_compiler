"""Regressions for PR #1: injected domains, canonical identity and inventory."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from itertools import permutations
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import generic
import reference
from cases import make_cases, model, job
from domain_packages import DomainRegistry, builtin_registry
from validation import PROFILE, ValidationError, _fingerprint, _integer, _keys, _list, _unique
from verify_manifest import check_manifest

HERE = Path(__file__).resolve().parent
RUST = HERE / "rust_kernel/target/release/ir-validation-kernel"


class InspectionDomain:
    """Third adapter with its own schema; never edits the compiler/registry code.

    Work orders acquire one inspection bay. This deliberately does not inherit
    TaskAssetDomain or use the fleet/missions/machines/jobs table aliases.
    """
    domain = "inspection"

    def validate_business(self, raw):
        _keys(raw, {"schema", "profile", "domain", "model_id", "revision", "time_unit",
                    "horizon", "work_orders"}, "inspection")
        orders = _list(raw.get("work_orders"), "work orders")
        _unique(orders, "work orders")
        for order in orders:
            _keys(order, {"id", "processing_ticks"}, "work order")
            _integer(order.get("processing_ticks"), "processing ticks")
        return deepcopy(raw)

    def lower_core(self, business):
        return {"schema": "core/v1", "profile": PROFILE, "time_unit": "tick",
                "model_id": business["model_id"], "revision": business["revision"],
                "horizon": business["horizon"], "business_fingerprint": _fingerprint(business),
                "assets": [], "resources": [{"id": "bay", "kind": "capacity", "initial": 1}],
                "processes": [{"id": order["id"], "candidates": [], "required_state": 0,
                               "finish_state": 0, "needs": {"bay": 1},
                               "duration": [order["processing_ticks"]] * 2, "after": [],
                               "release": 0, "interruptible": False, "repeat_delay": None}
                              for order in business["work_orders"]],
                "events": [], "source_map": {"process:" + order["id"]: f"/work_orders/{i}"
                                             for i, order in enumerate(business["work_orders"])}}


def third_domain_input():
    return {"schema": "business/v1", "profile": PROFILE, "time_unit": "tick",
            "domain": "inspection", "model_id": "external-adapter", "revision": "1",
            "horizon": 10, "work_orders": [{"id": "one", "processing_ticks": 3},
                                           {"id": "two", "processing_ticks": 2}]}


class ReviewRegressions(unittest.TestCase):
    def three_engines(self, plan):
        py = generic.semantic_result(generic.run_plan(plan, seed=7))
        ref = generic.semantic_result(reference.run_plan(plan, seed=7))
        output = subprocess.run([str(RUST)], input=json.dumps({"plan": plan.to_dict(), "seeds": [7]}),
                                text=True, capture_output=True, check=True)
        rust = generic.semantic_result(json.loads(output.stdout)["results"][0])
        self.assertEqual(py, ref)
        self.assertEqual(rust, ref)
        return py

    def test_third_adapter_injected_without_compiler_changes(self):
        raw = third_domain_input()
        registry = DomainRegistry([InspectionDomain()])
        business = generic.compile_business(raw, registry=registry)
        core = generic.lower_core(business, registry=registry)
        plan = generic.compile_plan(core)
        self.assertEqual(plan, generic.build_plan(raw, registry=registry))
        result = self.three_engines(plan)
        self.assertEqual(result["started"], [0, 3])
        self.assertEqual(result["finished"], [3, 5])
        self.assertEqual(result["resources"], [1])
        self.assertEqual(raw, third_domain_input())

    def test_registries_are_isolated_and_reject_duplicate_names(self):
        custom = DomainRegistry([*builtin_registry().adapters.values(), InspectionDomain()])
        generic.build_plan(third_domain_input(), registry=custom)
        with self.assertRaisesRegex(ValidationError, "unsupported domain"):
            generic.build_plan(third_domain_input())
        with self.assertRaisesRegex(ValidationError, "duplicate domain adapter"):
            DomainRegistry([InspectionDomain(), InspectionDomain()])
        with self.assertRaises(TypeError):
            custom.adapters["extra"] = InspectionDomain()

    def test_adapter_validation_and_backend_capability_still_apply(self):
        registry = DomainRegistry([InspectionDomain()])
        raw = third_domain_input()
        raw["work_orders"][0]["processing_ticks"] = -1
        with self.assertRaises(ValidationError):
            generic.build_plan(raw, registry=registry)
        raw = third_domain_input()
        raw["profile"] = "unknown"
        with self.assertRaisesRegex(ValidationError, "unsupported Business"):
            generic.build_plan(raw, registry=registry)
        core = generic.lower_core(third_domain_input(), registry=registry)
        core["events"].append({"id": "invented", "time": 0, "op": "invented_operation",
                               "target": "bay", "value": 1, "trigger": None, "repeat_every": None})
        with self.assertRaisesRegex(ValidationError, "unknown operation"):
            generic.compile_plan(core)

    def test_compiler_has_no_concrete_domain_vocabulary(self):
        import ast
        literals = {node.value for node in ast.walk(ast.parse(Path(generic.__file__).read_text()))
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertFalse(literals & {"aircraft", "production", "fleet", "missions", "maintenance",
                                     "machines", "jobs", "outages"})

    def test_needs_permutations_keep_all_three_identities(self):
        raw = model("needs-order", resources=[{"id": "Z", "kind": "capacity", "initial": 1},
                                             {"id": "crew", "kind": "capacity", "initial": 1},
                                             {"id": "备件", "kind": "stock", "initial": 1}],
                    work=[job("work", 2, needs={"备件": 1, "crew": 1, "Z": 1})])
        original = generic.build_plan(raw)
        expected = self.three_engines(original)
        for names in permutations(["Z", "crew", "备件"]):
            changed = deepcopy(raw)
            changed["missions"][0]["needs"] = {name: 1 for name in names}
            plan = generic.build_plan(changed)
            self.assertEqual(plan.business_fingerprint, original.business_fingerprint)
            self.assertEqual(plan.core_fingerprint, original.core_fingerprint)
            self.assertEqual(plan.to_dict(), original.to_dict())
            self.assertEqual(plan.processes[0].needs, ((0, 1), (1, 1), (2, 1)))
            self.assertEqual(self.three_engines(plan), expected)

    def test_direct_core_and_json_object_order_are_canonical(self):
        raw = make_cases()[2]["business"]
        reordered = json.loads(json.dumps(raw), object_pairs_hook=lambda pairs: dict(reversed(pairs)))
        self.assertEqual(generic.build_plan(raw), generic.build_plan(reordered))
        core = generic.lower_core(raw)
        other = deepcopy(core)
        for process in other["processes"]:
            process["needs"] = dict(reversed(list(process["needs"].items())))
        self.assertEqual(generic.compile_plan(core), generic.compile_plan(other))

    def test_meaningful_candidate_array_order_is_preserved(self):
        raw = model("candidate-order", assets=[{"id": "A"}, {"id": "B"}],
                    work=[job("work", 2, eligible=["A", "B"])])
        first = generic.build_plan(raw)
        raw["missions"][0]["eligible"].reverse()
        second = generic.build_plan(raw)
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(self.three_engines(first)["selected"], [0])
        self.assertEqual(self.three_engines(second)["selected"], [1])

    def test_manifest_accepts_exact_file_and_rejects_missing_or_corrupt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / "a.py"
            data = b"print(1)\n"
            local.write_bytes(data)
            manifest = {"files": {"a.py": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}
            self.assertTrue(check_manifest(root, manifest, {"a.py"})["passed"])
            local.write_bytes(b"print(2)\n")
            self.assertFalse(check_manifest(root, manifest, {"a.py"})["passed"])
            local.unlink()
            self.assertFalse(check_manifest(root, manifest, {"a.py"})["passed"])

    def test_manifest_rejects_untracked_and_transfer_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, inventory in [("untracked.json", set()), ("oracle.json.gz.base64", {"oracle.json.gz.base64"})]:
                (root / name).write_bytes(b"123")
                manifest = {"files": {name: {"bytes": 3, "sha256": hashlib.sha256(b"123").hexdigest()}}}
                self.assertFalse(check_manifest(root, manifest, inventory)["passed"])


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"test": test.id(), "passed": True})

    def addFailure(self, test, error):
        super().addFailure(test, error)
        self.records.append({"test": test.id(), "passed": False, "error": self._exc_info_to_string(error, test)})

    def addError(self, test, error):
        super().addError(test, error)
        self.records.append({"test": test.id(), "passed": False, "error": self._exc_info_to_string(error, test)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "results/review_fix_results.json")
    parser.add_argument("--rust", type=Path, default=RUST)
    args = parser.parse_args()
    RUST = args.rust.resolve()
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordedResult).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(ReviewRegressions))
    source_paths = [HERE / "generic.py", HERE / "validation.py", HERE / "verify_manifest.py",
                    Path(__file__), *sorted((HERE / "domain_packages").glob("*.py"))]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"reviewed_commit": "00b175ab5f804730f5f6713828fcdcfe4b2295ca",
                                     "passed": result.wasSuccessful(), "tests_run": result.testsRun,
                                     "tests": result.records,
                                     "source_files_sha256": {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
                                     "rust_binary_sha256": hashlib.sha256(RUST.read_bytes()).hexdigest()}, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
