"""Keep the historical pairing source identity distinct from a new engine revision."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest

from experiments.simlox_pairing.provenance import (
    BASELINE, BASELINE_BUILD_SHA256, DECLARED_BASELINE_OVERRIDE_SHA256,
    DECLARED_MODIFIED_BASELINE_SOURCE_SHA256, DECLARED_NONBASELINE_SOURCE_SHA256,
    ROOT, _verified_engine_sources,
)
from tests.conformance.test_simlox_pairing_provenance import _make_source_repo


class DeclaredEngineDeltaTests(unittest.TestCase):
    def test_integrated_checkout_keeps_reviewed_additions_and_frozen_baseline(self):
        # This verifies source bytes only; imported SDK/runtime acceptance is a
        # separate test and requires the supported existing SimPy environment.
        identity = _verified_engine_sources(
            ROOT, BASELINE,
            declared_nonbaseline_sources=DECLARED_NONBASELINE_SOURCE_SHA256,
            declared_baseline_overrides=DECLARED_BASELINE_OVERRIDE_SHA256,
            declared_modified_baseline_sources=DECLARED_MODIFIED_BASELINE_SOURCE_SHA256,
        )
        self.assertEqual(identity["build_fingerprint"], BASELINE_BUILD_SHA256)
        self.assertEqual(identity["declared_baseline_overrides"],
                         DECLARED_BASELINE_OVERRIDE_SHA256)
        self.assertEqual(identity["declared_modified_baseline_source_files"],
                         DECLARED_MODIFIED_BASELINE_SOURCE_SHA256)
        self.assertIn("src/sim_engine_compiler/ir/bounded.py",
                      identity["declared_nonbaseline_source_files"])

    def test_pr561_reliability_modules_are_reviewed_additions(self):
        expected = {
            "src/sim_engine_compiler/domains/aircraft_support/reliability.py": (
                "81609ca387dcaa697a4277226b6062fb59feec5d57d43f32b8aec22a9affff86"
            ),
            "src/sim_engine_compiler/ir/reliability.py": (
                "991de1953f2c2aefb70513ad0208d1aa4e76d9ba7792eb9de826aa0ebf8e6f36"
            ),
        }
        for key, digest in expected.items():
            self.assertEqual(DECLARED_NONBASELINE_SOURCE_SHA256[key], digest)
        identity = _verified_engine_sources(
            ROOT, BASELINE,
            declared_nonbaseline_sources=DECLARED_NONBASELINE_SOURCE_SHA256,
            declared_baseline_overrides=DECLARED_BASELINE_OVERRIDE_SHA256,
            declared_modified_baseline_sources=DECLARED_MODIFIED_BASELINE_SOURCE_SHA256,
        )
        self.assertEqual(identity["build_fingerprint"], BASELINE_BUILD_SHA256)
        for key, digest in expected.items():
            self.assertEqual(identity["declared_nonbaseline_source_files"][key], digest)
            self.assertIn(key, identity["declared_nonbaseline_source_modes"])
            self.assertEqual(
                identity["declared_nonbaseline_executed_source_files"][key],
                hashlib.sha256((ROOT / key).read_bytes()).hexdigest(),
            )

    def test_registered_additions_preserve_membership_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            baseline = _verified_engine_sources(root, revision)
            added = root / "src/sim_engine_compiler/added.py"
            key = "src/sim_engine_compiler/added.py"
            added.write_bytes(b"reviewed = True\n")
            declared = {key: hashlib.sha256(added.read_bytes()).hexdigest()}
            extended = _verified_engine_sources(
                root, revision, declared_nonbaseline_sources=declared
            )
            self.assertEqual(extended["build_fingerprint"], baseline["build_fingerprint"])
            self.assertNotEqual(
                extended["checkout_source_membership_fingerprint"],
                baseline["checkout_source_membership_fingerprint"],
            )
            self.assertEqual(extended["declared_nonbaseline_source_files"], declared)

            unregistered = root / "src/sim_engine_compiler/unregistered.py"
            unregistered.write_bytes(b"unexpected = True\n")
            with self.assertRaisesRegex(ValueError, "membership differs"):
                _verified_engine_sources(
                    root, revision, declared_nonbaseline_sources=declared
                )
            unregistered.unlink()

            added.write_bytes(b"reviewed = False\n")
            with self.assertRaisesRegex(ValueError, "differs from pinned content"):
                _verified_engine_sources(
                    root, revision, declared_nonbaseline_sources=declared
                )
            added.unlink()
            with self.assertRaisesRegex(ValueError, "membership differs"):
                _verified_engine_sources(
                    root, revision, declared_nonbaseline_sources=declared
                )

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

    def test_package_override_and_engine_delta_are_independently_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            engine_key = "src/sim_engine_compiler/engine.py"
            (root / engine_key).write_bytes(b"first = 1\nsecond = 3\n")
            (root / "pyproject.toml").write_bytes(b"[project]\nname = 'new-package'\n")
            modified = {engine_key: hashlib.sha256((root / engine_key).read_bytes()).hexdigest()}
            overrides = {"pyproject.toml": hashlib.sha256((root / "pyproject.toml").read_bytes()).hexdigest()}
            kwargs = dict(declared_modified_baseline_sources=modified,
                          declared_baseline_overrides=overrides)
            identity = _verified_engine_sources(root, revision, **kwargs)
            for path in (root / engine_key, root / "pyproject.toml"):
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
            crlf = _verified_engine_sources(root, revision, **kwargs)
            self.assertEqual(crlf["build_fingerprint"], identity["build_fingerprint"])
            self.assertNotEqual(crlf["executed_source_fingerprint"],
                                identity["executed_source_fingerprint"])
            (root / engine_key).write_bytes(b"first = 1\r\nsecond = 3\n")
            with self.assertRaisesRegex(ValueError, "differs from pinned content"):
                _verified_engine_sources(root, revision, **kwargs)

    def test_absent_or_duplicate_modified_baseline_declarations_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            with self.assertRaisesRegex(ValueError, "absent from frozen baseline"):
                _verified_engine_sources(
                    root, revision,
                    declared_modified_baseline_sources={"src/sim_engine_compiler/missing.py": "0" * 64},
                )
            key = "src/sim_engine_compiler/engine.py"
            declared = {key: hashlib.sha256((root / key).read_bytes()).hexdigest()}
            with self.assertRaisesRegex(ValueError, "overlap baseline overrides"):
                _verified_engine_sources(
                    root, revision, declared_modified_baseline_sources=declared,
                    declared_baseline_overrides=declared,
                )
