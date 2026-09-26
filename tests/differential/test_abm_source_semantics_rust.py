from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from sim_engine_compiler import compile_model, run_abm_plan
from sim_engine_compiler.ir.abm import ABM_PLAN_VERSION, canonical_digest
from sim_engine_compiler.reference import AbmRuntimeError
from tests.fixtures.abm_source_semantics.cases import cases, setup_lifecycle_case

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rust" / "runtime" / "Cargo.toml"
COORDINATE_TOLERANCE = 1e-12


def _cargo() -> str:
    cargo = shutil.which("cargo")
    if cargo:
        return cargo
    fallback = Path.home() / ".cargo" / "bin" / "cargo"
    if fallback.exists():
        return str(fallback)
    raise AssertionError("Rust source-semantics differential tests require cargo")


def _equal_with_frozen_coordinate_tolerance(
    testcase: unittest.TestCase, expected: dict, actual: dict
) -> None:
    expected = copy.deepcopy(expected)
    actual = copy.deepcopy(actual)
    testcase.assertEqual(len(expected["state"]["agents"]), len(actual["state"]["agents"]))
    for left, right in zip(expected["state"]["agents"], actual["state"]["agents"], strict=True):
        testcase.assertEqual(left["id"], right["id"])
        for field in ("x", "y"):
            testcase.assertAlmostEqual(left[field], right[field], delta=COORDINATE_TOLERANCE)
            right[field] = left[field]
    testcase.assertEqual(len(expected["events"]), len(actual["events"]))
    for left, right in zip(expected["events"], actual["events"], strict=True):
        testcase.assertEqual((left["kind"], left["entity"]), (right["kind"], right["entity"]))
        coordinate_fields: tuple[str, ...] = ()
        if left["kind"] == "move_attempt":
            coordinate_fields = ("from", "trial_position")
        elif left["kind"] == "moved":
            coordinate_fields = ("from", "to")
        elif left["kind"] == "born":
            for field in ("x", "y"):
                testcase.assertAlmostEqual(
                    left["details"][field], right["details"][field], delta=COORDINATE_TOLERANCE
                )
                right["details"][field] = left["details"][field]
        for field in coordinate_fields:
            testcase.assertEqual(len(left["details"][field]), len(right["details"][field]))
            for index in range(len(left["details"][field])):
                testcase.assertAlmostEqual(
                    left["details"][field][index],
                    right["details"][field][index],
                    delta=COORDINATE_TOLERANCE,
                )
                right["details"][field][index] = left["details"][field][index]
    testcase.assertEqual(expected, actual)


class SchellingSourceRustDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            [
                _cargo(),
                "+1.90.0",
                "build",
                "--quiet",
                "--release",
                "--no-default-features",
                "--manifest-path",
                str(MANIFEST),
                "--bin",
                "sim-engine-runtime",
            ],
            cwd=ROOT,
            check=True,
        )
        executable = "sim-engine-runtime.exe" if __import__("os").name == "nt" else "sim-engine-runtime"
        cls.binary = ROOT / "rust" / "runtime" / "target" / "release" / executable
        cls.tempdir = tempfile.TemporaryDirectory(prefix="schelling-source-rust-")

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def _paths(self, case: dict) -> tuple[Path, Path, Path]:
        base = Path(self.tempdir.name) / case.get("case_id", "setup-lifecycle")
        plan_path = base.with_suffix(".plan.json")
        tape_path = base.with_suffix(".tape.json")
        output_path = base.with_suffix(".result.json")
        plan_path.write_text(
            json.dumps(compile_model(case["model"]).plan.to_dict(), sort_keys=True, separators=(",", ":"))
        )
        tape_path.write_text(json.dumps(case["random_tape"], sort_keys=True, separators=(",", ":")))
        return plan_path, tape_path, output_path

    def _run(self, case: dict, *, check: bool = True) -> tuple[subprocess.CompletedProcess[str], dict | None]:
        plan_path, tape_path, output_path = self._paths(case)
        process = subprocess.run(
            [str(self.binary), str(plan_path), str(output_path), "--seed", "0", "--random-tape", str(tape_path)],
            cwd=ROOT,
            check=check,
            capture_output=True,
            text=True,
        )
        result = json.loads(output_path.read_text()) if process.returncode == 0 else None
        return process, result

    def _load_invalid_payload(self, payload: dict, name: str) -> subprocess.CompletedProcess[str]:
        base = Path(self.tempdir.name) / name
        plan_path = base.with_suffix(".plan.json")
        tape_path = base.with_suffix(".tape.json")
        output_path = base.with_suffix(".result.json")
        envelope = {
            "version": ABM_PLAN_VERSION,
            "fingerprint": canonical_digest({"version": ABM_PLAN_VERSION, "payload": payload}),
            "payload": payload,
        }
        plan_path.write_text(json.dumps(envelope, sort_keys=True, separators=(",", ":")))
        tape_path.write_text(json.dumps({"schema_version": "abm-random-tape/v1", "requests": []}))
        return subprocess.run(
            [str(self.binary), str(plan_path), str(output_path), "--random-tape", str(tape_path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_eight_success_hand_cases_match_python_complete_results(self):
        for case in cases():
            if "expected_error" in case:
                continue
            with self.subTest(case=case["case_id"]):
                expected = run_abm_plan(
                    compile_model(case["model"]).plan, random_tape=case["random_tape"]
                )
                _, actual = self._run(case)
                self.assertIsNotNone(actual)
                _equal_with_frozen_coordinate_tolerance(self, expected, actual)

    def test_zero_denominator_fails_in_both_backends(self):
        case = next(item for item in cases() if item["case_id"] == "zero-denominator")

        with self.assertRaises(AbmRuntimeError) as python_error:
            run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
        process, result = self._run(case, check=False)

        self.assertIsNone(result)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(getattr(python_error.exception, "code", None), "metric_zero_denominator")
        self.assertIn("metric_zero_denominator", process.stderr)

    def test_setup_sprout_lifecycle_matches_python(self):
        case = {"case_id": "setup-lifecycle", **setup_lifecycle_case()}
        expected = run_abm_plan(
            compile_model(case["model"]).plan, random_tape=case["random_tape"]
        )

        _, actual = self._run(case)

        self.assertIsNotNone(actual)
        _equal_with_frozen_coordinate_tolerance(self, expected, actual)

    def test_rust_rejects_missing_mismatched_extra_tape_and_budget_exhaustion(self):
        base = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")
        variants: list[tuple[dict, str]] = []
        missing = copy.deepcopy(base)
        missing["case_id"] = "rust-tape-missing"
        missing["random_tape"]["requests"].pop()
        variants.append((missing, "random_tape_missing"))
        mismatch = copy.deepcopy(base)
        mismatch["case_id"] = "rust-tape-mismatch"
        mismatch["random_tape"]["requests"][0]["distribution"] = "integer"
        variants.append((mismatch, "random_tape_mismatch"))
        extra = copy.deepcopy(base)
        extra["case_id"] = "rust-tape-unused"
        extra["random_tape"]["requests"].append(copy.deepcopy(extra["random_tape"]["requests"][-1]))
        extra["random_tape"]["requests"][-1]["occurrence"] = 1
        variants.append((extra, "random_tape_unused"))
        malformed = copy.deepcopy(base)
        malformed["case_id"] = "rust-tape-invalid-distribution"
        malformed["random_tape"]["requests"][0].update(
            {"distribution": "normal", "args": [], "value": 0}
        )
        variants.append((malformed, "invalid_random_tape"))
        overflow = copy.deepcopy(base)
        overflow["case_id"] = "rust-tape-occurrence-overflow"
        overflow["random_tape"]["requests"][0]["occurrence"] = 2**63
        variants.append((overflow, "invalid_random_tape"))

        budget = copy.deepcopy(next(item for item in cases() if item["case_id"] == "rejected-attempt-carries-state"))
        budget["case_id"] = "rust-attempt-budget"
        budget["model"]["phases"][0]["operations"][0]["local_rejection"]["attempt_budget"] = 1
        budget["random_tape"]["requests"] = budget["random_tape"]["requests"][:2]
        variants.append((budget, "random_attempt_budget_exhausted"))

        for case, code in variants:
            with self.subTest(code=code):
                process, result = self._run(case, check=False)
                self.assertIsNone(result)
                self.assertNotEqual(process.returncode, 0)
                self.assertIn(code, process.stderr)

    def test_non_coordinate_float_difference_is_never_tolerated(self):
        case = next(item for item in cases() if item["case_id"] == "weighted-metric-witness")
        result = run_abm_plan(compile_model(case["model"]).plan, random_tape=case["random_tape"])
        mutant = copy.deepcopy(result)
        mutant["metrics"]["source_percent_similar"] += 1e-13

        with self.assertRaises(AssertionError):
            _equal_with_frozen_coordinate_tolerance(self, result, mutant)

    def test_rust_loader_rejects_invalid_extension_and_unsupported_combinations(self):
        base = next(item for item in cases() if item["case_id"] == "own-patch-acceptance")["model"]
        mutations: list[tuple[str, dict]] = []
        unknown = copy.deepcopy(base)
        unknown["source_semantics"]["schema_version"] = "abm-source-semantics/v2"
        mutations.append(("unknown-source-schema", unknown))
        post_tick = copy.deepcopy(base)
        post_tick["source_semantics"]["stop_timing"] = "after_tick"
        mutations.append(("wrong-stop-timing", post_tick))
        null_extension = copy.deepcopy(base)
        null_extension["source_semantics"] = None
        mutations.append(("null-source-extension", null_extension))
        null_selector = copy.deepcopy(base)
        null_selector["phases"][0]["where"] = None
        mutations.append(("null-selector", null_selector))
        random_stop = copy.deepcopy(base)
        random_stop["stop_conditions"] = [
            {
                "id": "random-stop",
                "when": {
                    "op": "random",
                    "distribution": "bernoulli",
                    "address": "invalid.random-stop",
                    "args": [0.5],
                },
            }
        ]
        mutations.append(("random-stop", random_stop))
        finite = copy.deepcopy(base)
        finite["topology"]["kind"] = "finite"
        mutations.append(("finite-local-rejection", finite))
        buffered = copy.deepcopy(base)
        buffered["phases"][0]["commit_mode"] = "buffered"
        mutations.append(("buffered-local-rejection", buffered))
        bad_bounds = copy.deepcopy(base)
        bad_bounds["phases"][0]["operations"][0]["local_rejection"]["turn_bounds"] = [0, 180]
        mutations.append(("wrong-turn-bounds", bad_bounds))
        zero_budget = copy.deepcopy(base)
        zero_budget["phases"][0]["operations"][0]["local_rejection"]["attempt_budget"] = 0
        mutations.append(("zero-attempt-budget", zero_budget))
        overflow_budget = copy.deepcopy(base)
        overflow_budget["phases"][0]["operations"][0]["local_rejection"]["attempt_budget"] = 2**63
        mutations.append(("overflow-attempt-budget", overflow_budget))

        for name, payload in mutations:
            with self.subTest(name=name):
                process = self._load_invalid_payload(payload, name)
                self.assertNotEqual(process.returncode, 0)
                self.assertFalse(Path(self.tempdir.name, f"{name}.result.json").exists())


if __name__ == "__main__":
    unittest.main()
