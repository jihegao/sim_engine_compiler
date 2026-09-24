from __future__ import annotations

import copy
import os
from pathlib import Path
import subprocess
import unittest

from demo.validation_app import _compare, _input, compare


ROOT = Path(__file__).resolve().parents[2]


class ValidationAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for manifest, binary in (
            ("rust/compiler/Cargo.toml", "sim-engine-compiler-aot"),
            ("rust/runtime/Cargo.toml", "sim-engine-runtime"),
        ):
            subprocess.run(
                ["cargo", "build", "--release", "--locked", "--manifest-path", manifest,
                 "--bin", binary],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )

    def test_b1_o5_and_cache_preserve_full_results_across_threads(self):
        report = compare({
            "case": "B1", "seed": 3, "samples": 2, "threads": 2,
            "profile": "O5", "mlir_index": False, "plan_cache": True,
        })
        self.assertTrue(all(item["equal"] for item in report["correctness"].values()))
        self.assertEqual([arm["cache_hit"] for arm in report["arms"]],
                         [False, False, False, True])
        self.assertEqual({arm["worker_threads"] for arm in report["arms"]}, {2})
        self.assertTrue(report["engine"]["runtime_version"].startswith("sim-engine-runtime "))

    def test_b3_and_f35_o5_preserve_business_results(self):
        for case in ("B3", "F35"):
            with self.subTest(case=case):
                report = compare({
                    "case": case, "seed": 0, "samples": 1, "threads": 1,
                    "profile": "O5", "mlir_index": False, "plan_cache": False,
                })
                self.assertTrue(report["correctness"]["algorithm"]["equal"])
                self.assertEqual(report["contract"]["observation_level"], "full")

    def test_indexed_path_if_pinned_mlir_is_available(self):
        if not (os.environ.get("SIM_ENGINE_MLIR_PLUGIN_DIR")
                and os.environ.get("SIM_ENGINE_MLIR_OPT")):
            self.skipTest("pinned MLIR plugins are not configured")
        report = compare({
            "case": "B1", "seed": 0, "samples": 1, "threads": 1,
            "profile": "O5", "mlir_index": True, "plan_cache": False,
        })
        self.assertTrue(report["correctness"]["algorithm"]["equal"])
        self.assertTrue(report["arms"][1]["index_enabled"])

    def test_first_divergence_is_reported_alongside_results(self):
        sample = {"sample_index": 0, "seed": 0, "result": {
            "plan_fingerprint": "left", "seed": 0, "time": 1,
            "stop_reason": "horizon", "sample_requests": [],
            "trace": [{"time": 1, "rule_id": "dispatch", "kind": "start"}],
            "metrics": {}, "terminal_state": {},
        }}
        left = {"batch": {"samples": [sample]}}
        right = copy.deepcopy(left)
        right["batch"]["samples"][0]["result"]["trace"][0]["kind"] = "cancel"
        difference = _compare(left, right)
        self.assertFalse(difference["equal"])
        self.assertIn("trace[0].kind", difference["path"])
        self.assertEqual(difference["rule_id"], "dispatch")

    def test_unsupported_combination_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "not a supported combined path"):
            _input({"case": "B1", "profile": "O5", "mlir_index": True,
                    "plan_cache": True})


if __name__ == "__main__":
    unittest.main()
