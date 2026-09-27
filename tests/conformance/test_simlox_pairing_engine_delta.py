"""Keep the historical pairing source identity distinct from a new engine revision."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from experiments.simlox_pairing.provenance import _verified_engine_sources
from tests.conformance.test_simlox_pairing_provenance import _make_source_repo


class DeclaredEngineDeltaTests(unittest.TestCase):
    def test_delta_is_pinned_without_rewriting_frozen_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            source = root / "src/sim_engine_compiler/engine.py"
            baseline = _verified_engine_sources(root, revision)
            source.write_bytes(b"first = 1\nsecond = 3\n")
            declared = {"src/sim_engine_compiler/engine.py": hashlib.sha256(
                source.read_bytes()).hexdigest()}
            changed = _verified_engine_sources(
                root, revision, declared_modified_baseline_sources=declared
            )
            self.assertEqual(changed["build_fingerprint"], baseline["build_fingerprint"])
            self.assertNotEqual(changed["executed_source_fingerprint"],
                                baseline["executed_source_fingerprint"])
            self.assertEqual(changed["declared_modified_baseline_source_files"], declared)
            source.write_bytes(b"first = 1\nsecond = 4\n")
            with self.assertRaisesRegex(ValueError, "differs from pinned content"):
                _verified_engine_sources(
                    root, revision, declared_modified_baseline_sources=declared
                )
