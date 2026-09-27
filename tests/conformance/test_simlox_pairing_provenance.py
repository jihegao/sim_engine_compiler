from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path, PureWindowsPath

from experiments.simlox_pairing.provenance import (
    DECLARED_NONBASELINE_SOURCE_SHA256,
    DEFAULT_ARCHIVE,
    MANIFEST_SHA256,
    _canonical_path_key,
    _verified_engine_sources,
    load_handoff,
    source_identity,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _make_source_repo(root: Path) -> str:
    source = root / "src/sim_engine_compiler"
    source.mkdir(parents=True)
    (source / "engine.py").write_bytes(b"first = 1\nsecond = 2\n")
    (root / "pyproject.toml").write_bytes(b"[project]\nname = 'portable-test'\n")
    _git(root, "init", "-q")
    _git(root, "config", "core.autocrlf", "false")
    _git(root, "add", "src/sim_engine_compiler/engine.py", "pyproject.toml")
    _git(
        root,
        "-c",
        "user.name=Pairing Test",
        "-c",
        "user.email=pairing@example.invalid",
        "commit",
        "-q",
        "-m",
        "baseline",
    )
    return _git(root, "rev-parse", "HEAD")


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
        self.assertIn(
            "src/sim_engine_compiler/reference/simpy_runtime.py",
            identity["source_files"],
        )
        self.assertNotEqual(
            identity["build_fingerprint"], identity["consumer_source_fingerprint"]
        )
        self.assertIsNone(identity["identity_pr20_dependency"])
        self.assertEqual(
            identity["declared_nonbaseline_source_files"],
            DECLARED_NONBASELINE_SOURCE_SHA256,
        )
        self.assertTrue(identity["checkout_source_membership_fingerprint"])

    def test_source_keys_are_posix_for_windows_and_host_path_objects(self):
        self.assertEqual(
            _canonical_path_key(
                PureWindowsPath(r"src\sim_engine_compiler\reference\simpy_runtime.py")
            ),
            "src/sim_engine_compiler/reference/simpy_runtime.py",
        )
        identity = source_identity()
        self.assertTrue(all("\\" not in key for key in identity["source_files"]))
        self.assertTrue(
            all("\\" not in key for key in identity["executed_source_files"])
        )

    def test_strict_whole_file_crlf_checkout_preserves_blob_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            exact = _verified_engine_sources(root, revision)
            for relative in (
                Path("src/sim_engine_compiler/engine.py"),
                Path("pyproject.toml"),
            ):
                path = root / relative
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

            crlf = _verified_engine_sources(root, revision)

        self.assertEqual(crlf["build_fingerprint"], exact["build_fingerprint"])
        self.assertNotEqual(
            crlf["executed_source_fingerprint"], exact["executed_source_fingerprint"]
        )
        self.assertEqual(
            set(crlf["executed_source_modes"].values()),
            {"controlled_whole_file_lf_to_crlf_checkout"},
        )

    def test_mixed_newlines_and_bare_cr_are_rejected_instead_of_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            source = root / "src/sim_engine_compiler/engine.py"
            source.write_bytes(b"first = 1\r\nsecond = 2\n")
            with self.assertRaisesRegex(ValueError, "differs from frozen baseline"):
                _verified_engine_sources(root, revision)
            source.write_bytes(b"first = 1\rsecond = 2\r")
            with self.assertRaisesRegex(ValueError, "differs from frozen baseline"):
                _verified_engine_sources(root, revision)

    def test_dirty_source_content_is_rejected_even_when_baseline_blob_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            (root / "src/sim_engine_compiler/engine.py").write_bytes(
                b"first = 999\nsecond = 2\n"
            )
            with self.assertRaisesRegex(ValueError, "differs from frozen baseline"):
                _verified_engine_sources(root, revision)

    def test_added_or_deleted_engine_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            extra = root / "src/sim_engine_compiler/extra.py"
            extra.write_bytes(b"unexpected = True\n")
            with self.assertRaisesRegex(ValueError, "membership differs"):
                _verified_engine_sources(root, revision)
            extra.unlink()
            (root / "src/sim_engine_compiler/engine.py").unlink()
            with self.assertRaisesRegex(ValueError, "membership differs"):
                _verified_engine_sources(root, revision)

    def test_declared_nonbaseline_sources_are_exact_and_do_not_change_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            revision = _make_source_repo(root)
            baseline = _verified_engine_sources(root, revision)
            extra = root / "src/sim_engine_compiler/extra.py"
            extra.write_bytes(b"declared = True\n")
            declared = {"src/sim_engine_compiler/extra.py": "9" * 64}
            with self.assertRaisesRegex(ValueError, "differs from pinned content"):
                _verified_engine_sources(
                    root,
                    revision,
                    declared_nonbaseline_sources=declared,
                )

            declared["src/sim_engine_compiler/extra.py"] = hashlib.sha256(
                extra.read_bytes()
            ).hexdigest()
            extended = _verified_engine_sources(
                root,
                revision,
                declared_nonbaseline_sources=declared,
            )
            self.assertEqual(extended["build_fingerprint"], baseline["build_fingerprint"])
            self.assertNotEqual(
                extended["checkout_source_membership_fingerprint"],
                baseline["checkout_source_membership_fingerprint"],
            )

            extra.write_bytes(b"declared = False\n")
            with self.assertRaisesRegex(ValueError, "differs from pinned content"):
                _verified_engine_sources(
                    root,
                    revision,
                    declared_nonbaseline_sources=declared,
                )

            extra.unlink()
            with self.assertRaisesRegex(ValueError, "membership differs"):
                _verified_engine_sources(
                    root,
                    revision,
                    declared_nonbaseline_sources=declared,
                )

    def test_missing_baseline_object_fails_closed_without_using_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _make_source_repo(root)
            with self.assertRaisesRegex(ValueError, "fetch the exact baseline commit"):
                _verified_engine_sources(root, "0" * 40)
