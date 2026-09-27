from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.simlox_pairing.provenance import (
    DEFAULT_ARCHIVE,
    MANIFEST_SHA256,
    load_handoff,
    source_identity,
)


class FrozenPairingProvenanceTests(unittest.TestCase):
    def test_external_manifest_and_complete_portable_contract_are_verified(self):
        handoff = load_handoff()
        self.assertEqual(handoff["verification"]["manifest_sha256"], MANIFEST_SHA256)
        self.assertEqual(handoff["verification"]["intervals_per_case"], 72)
        self.assertFalse(handoff["verification"]["delivered_zip_verified"])
        self.assertFalse(handoff["verification"]["native_raw_evidence_rechecked_here"])

    def test_changed_archive_cannot_self_authorize_by_internal_hashes(self):
        raw = DEFAULT_ARCHIVE.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tampered.zip"
            path.write_bytes(raw + b"changed")
            with self.assertRaisesRegex(ValueError, "externally pinned"):
                load_handoff(path)

    def test_source_and_consumer_fingerprints_are_separate(self):
        identity = source_identity()
        self.assertEqual(len(identity["build_fingerprint"]), 64)
        self.assertIn("src/sim_engine_compiler/reference/simpy_runtime.py",
                      identity["source_files"])
        self.assertNotEqual(identity["build_fingerprint"],
                            identity["consumer_source_fingerprint"])
        self.assertIsNone(identity["identity_pr20_dependency"])
