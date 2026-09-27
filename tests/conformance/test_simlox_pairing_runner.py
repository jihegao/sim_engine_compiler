from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.simlox_pairing.check_tests import required_suite
from experiments.simlox_pairing.provenance import sha256
from experiments.simlox_pairing.run import execute_pairing


class PairingRunnerTests(unittest.TestCase):
    def test_runner_persists_independent_layers_results_and_all_72_interval_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "new-evidence"
            report = execute_pairing(output)
            self.assertEqual(report["equivalence_status"],
                             "matched_mapped_observables_not_full_equivalence")
            controls = json.loads(
                (output / "negative-controls.json").read_text(encoding="utf-8")
            )
            self.assertEqual(controls["status"], "passed")
            self.assertEqual(len(controls["controls"]), 4)
            self.assertTrue(controls["controls"][0]["same_integrals"])
            self.assertTrue(controls["controls"][0]["same_terminal_counts"])
            self.assertTrue(controls["controls"][0]["first_interval_discrepancy"]["path"]
                            .startswith("intervals[14]."))
            for case_id in ("A01", "A02"):
                case = report["cases"][case_id]
                self.assertEqual(case["status"], "matched")
                self.assertEqual(len(case["observed_72_intervals"]), 72)
                self.assertIsNone(case["first_discrepancy"])
                self.assertGreater(case["comparison_checks"], 600)
                for name, expected_hash in case["artifact_sha256"].items():
                    self.assertEqual(sha256((output / case_id / name).read_bytes()), expected_hash)
            index = json.loads(
                (output / "evidence-index.json").read_text(encoding="utf-8")
            )
            for name, expected_hash in index["files"].items():
                self.assertEqual(sha256((output / name).read_bytes()), expected_hash)

    def test_existing_evidence_directory_is_never_overwritten(self):
        with (tempfile.TemporaryDirectory() as directory,
              self.assertRaisesRegex(ValueError, "fresh evidence")):
            execute_pairing(Path(directory))

    def test_empty_required_module_is_rejected_instead_of_silent_zero_test_pass(self):
        with (patch("experiments.simlox_pairing.check_tests.unittest.defaultTestLoader.loadTestsFromName",
                    return_value=unittest.TestSuite()),
              self.assertRaisesRegex(ValueError, "no discoverable")):
            required_suite()
