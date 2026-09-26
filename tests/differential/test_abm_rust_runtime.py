from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from sim_engine_compiler import run_abm_plan
from sim_engine_compiler.ir import AbmTickPlan


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rust" / "runtime" / "Cargo.toml"
FIXTURES = ROOT / "tests" / "fixtures" / "abm"
EXPECTED_PLAN_FINGERPRINTS = {
    "fire": "b56674e373fa6ed4f8102ccf72e929759dddf4cf34949ffb9eb3046a7866c3cb",
    "schelling": "60c5820bc900c305822a3508b3d89b137e6ab74f90bf7d556e428116f33d97f9",
    "wolf-sheep": "5f8e20ff878fa7551b332cb774c9f3327265ef9ab9d210aa48e93c3c14f5caa9",
}
EXPECTED_FILE_SHA256 = {
    "fire": "2d657c75db4636aa1ca844644be9b416ca41a8e6f39047faaa5068bd8e2f794e",
    "schelling": "55c3f3635ca573664b380bb4069872c3ebf62e269b109d4e65eeaa9d33a2dd92",
    "wolf-sheep": "71d85bb27ad90126539f67f530e6e67aa8558ca4ebf176caf74ec827e7c2a196",
}


def _assert_abm_results_equal(
    testcase: unittest.TestCase, expected: dict, actual: dict
) -> None:
    """Compare only frozen continuous-coordinate fields with a tolerance."""
    expected = copy.deepcopy(expected)
    actual = copy.deepcopy(actual)
    testcase.assertEqual(len(expected["state"]["agents"]), len(actual["state"]["agents"]))
    for expected_agent, actual_agent in zip(
        expected["state"]["agents"], actual["state"]["agents"], strict=True
    ):
        testcase.assertEqual(expected_agent["id"], actual_agent["id"])
        for field in ("x", "y"):
            testcase.assertAlmostEqual(
                expected_agent[field], actual_agent[field], delta=1e-12
            )
            actual_agent[field] = expected_agent[field]
    testcase.assertEqual(len(expected["events"]), len(actual["events"]))
    for expected_event, actual_event in zip(
        expected["events"], actual["events"], strict=True
    ):
        testcase.assertEqual(expected_event["kind"], actual_event["kind"])
        if expected_event["kind"] == "moved":
            for field in ("from", "to"):
                testcase.assertEqual(
                    len(expected_event["details"][field]),
                    len(actual_event["details"][field]),
                )
                for index in range(len(expected_event["details"][field])):
                    testcase.assertAlmostEqual(
                        expected_event["details"][field][index],
                        actual_event["details"][field][index],
                        delta=1e-12,
                    )
                    actual_event["details"][field][index] = expected_event["details"][field][
                        index
                    ]
        elif expected_event["kind"] == "born":
            for field in ("x", "y"):
                testcase.assertAlmostEqual(
                    expected_event["details"][field],
                    actual_event["details"][field],
                    delta=1e-12,
                )
                actual_event["details"][field] = expected_event["details"][field]
    testcase.assertEqual(expected, actual)


def _cargo() -> str:
    cargo = shutil.which("cargo")
    if cargo:
        return cargo
    fallback = Path.home() / ".cargo" / "bin" / "cargo"
    if fallback.exists():
        return str(fallback)
    raise AssertionError("Rust ABM differential tests require cargo")


class AbmRustRuntimeDifferentialTests(unittest.TestCase):
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
        cls.tempdir = tempfile.TemporaryDirectory(prefix="sim-engine-abm-rust-")
        cls.paths = {name: FIXTURES / f"{name}-plan.json" for name in EXPECTED_PLAN_FINGERPRINTS}
        cls.plans = {name: json.loads(path.read_text()) for name, path in cls.paths.items()}

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def _run(self, case: str, seed: int) -> dict:
        output = Path(self.tempdir.name) / f"{case}-{seed}.json"
        subprocess.run(
            [str(self.binary), str(self.paths[case]), str(output), "--seed", str(seed)],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(output.read_text())

    def test_fixture_file_and_envelope_fingerprints_are_frozen(self):
        for case, path in self.paths.items():
            with self.subTest(case=case):
                self.assertEqual(self.plans[case]["fingerprint"], EXPECTED_PLAN_FINGERPRINTS[case])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), EXPECTED_FILE_SHA256[case])

    def test_three_python_generated_plans_match_exactly_for_twenty_seeds(self):
        for case, plan in self.plans.items():
            for seed in range(20):
                with self.subTest(case=case, seed=seed):
                    _assert_abm_results_equal(
                        self, run_abm_plan(plan, seed=seed), self._run(case, seed)
                    )

    def test_non_coordinate_float_difference_is_not_tolerated(self):
        expected = run_abm_plan(self.plans["schelling"], seed=3)
        actual = copy.deepcopy(expected)
        actual["random_requests"][0]["value"] += 1e-13

        with self.assertRaises(AssertionError):
            _assert_abm_results_equal(self, expected, actual)

    def test_inherit_heading_child_move_matches_without_random_request(self):
        payload = copy.deepcopy(self.plans["wolf-sheep"]["payload"])
        for phase in payload["phases"]:
            for operation in phase["operations"]:
                if operation.get("op") == "birth" and operation["child_move"] is not None:
                    operation["child_move"] = {
                        "mode": "inherit_heading",
                        "heading": None,
                        "address": None,
                        "distance": 1.0,
                    }
        plan = AbmTickPlan.create(payload).to_dict()
        path = Path(self.tempdir.name) / "wolf-sheep-inherit-plan.json"
        path.write_text(json.dumps(plan, sort_keys=True, separators=(",", ":")))
        output = Path(self.tempdir.name) / "wolf-sheep-inherit-0.json"
        subprocess.run(
            [str(self.binary), str(path), str(output), "--seed", "0"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        expected = run_abm_plan(plan, seed=0)
        actual = json.loads(output.read_text())
        _assert_abm_results_equal(self, expected, actual)
        self.assertTrue(any(event["kind"] == "born" for event in actual["events"]))
        self.assertFalse(
            any(
                request["address"].endswith("child-heading")
                for request in actual["random_requests"]
            )
        )

    def test_cli_batch_repeated_seeds_is_thread_count_invariant(self):
        seeds = (7, 0, 7, 1)
        outputs = []
        for workers in (1, 4):
            output = Path(self.tempdir.name) / f"batch-{workers}.json"
            subprocess.run(
                [
                    str(self.binary),
                    str(self.paths["schelling"]),
                    str(output),
                    "--seeds",
                    ",".join(map(str, seeds)),
                    "--worker-threads",
                    str(workers),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            outputs.append(json.loads(output.read_text()))
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual([item["sample_index"] for item in outputs[0]], list(range(4)))
        self.assertEqual(
            [item["result"] for item in outputs[0]],
            [run_abm_plan(self.plans["schelling"], seed=seed) for seed in seeds],
        )


if __name__ == "__main__":
    unittest.main()
