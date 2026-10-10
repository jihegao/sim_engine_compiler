"""Offline evidence selection checks; no simulation, timing, service or compiler."""
import copy
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.three_arm_v1 import publication


SOURCE = Path(__file__).resolve().parents[2] / "benchmarks/three_arm_v1/results/amd128-20260927"


class ThreeArmPublicationTests(unittest.TestCase):
    def _fixture(self, directory):
        folder = Path(directory)
        for name in ("EVIDENCE.json", "summary.json", publication.ARCHIVE_NAME):
            shutil.copyfile(SOURCE / name, folder / name)
        return folder

    def _rewrite_archive(self, folder, mutate):
        records = []
        with tarfile.open(folder / publication.ARCHIVE_NAME, "r:gz") as archive:
            for member in archive:
                records.append((copy.copy(member), archive.extractfile(member).read()))
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for member, data in mutate(records):
                archive.addfile(member, io.BytesIO(data))
        raw = gzip.compress(buffer.getvalue(), mtime=0)
        (folder / publication.ARCHIVE_NAME).write_bytes(raw)
        evidence_path = folder / "EVIDENCE.json"
        evidence = json.loads(evidence_path.read_text())
        evidence["committed_selection"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        evidence_path.write_text(json.dumps(evidence))

    def test_all_99_cells_recompute_identical_negative_summary_without_processes(self):
        with patch("subprocess.run", side_effect=AssertionError("offline check launched a process")):
            result = publication.verify_selection(SOURCE)
        self.assertEqual(result["complete_cells"], 99)
        self.assertEqual(result["formal_status"], "complete")
        classifications = [row["classification"] for group in result["groups"]
                           for row in group["comparisons"]]
        self.assertEqual(classifications.count("bounded-benefit"), 0)
        self.assertEqual(classifications.count("regression"), 29)
        self.assertEqual(classifications.count("no-demonstrated-benefit"), 4)

    def test_changed_archive_hash_rejects(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self._fixture(directory)
            archive = folder / publication.ARCHIVE_NAME
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "archive size or hash mismatch"):
                publication.verify_selection(folder)

    def test_recomputed_bundle_hash_cannot_hide_changed_catalog_member(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self._fixture(directory)
            def mutate(records):
                member, data = records[0]
                changed = data + b"\n"
                member.size = len(changed)
                return [(member, changed), *records[1:]]
            self._rewrite_archive(folder, mutate)
            with self.assertRaisesRegex(ValueError, "differs from original catalog"):
                publication.verify_selection(folder)

    def test_unsafe_duplicate_and_missing_members_reject_with_recomputed_bundle_hash(self):
        for kind in ("symlink", "duplicate", "traversal", "missing"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                folder = self._fixture(directory)
                def mutate(records):
                    member, data = records[0]
                    if kind == "symlink":
                        member.type = tarfile.SYMTYPE
                        member.linkname = "../../escape"
                        member.size = 0
                        return [(member, b""), *records[1:]]
                    if kind == "duplicate":
                        return records + [(copy.copy(member), data)]
                    if kind == "traversal":
                        member.name = "../escape"
                        return [(member, data), *records[1:]]
                    return records[1:]
                self._rewrite_archive(folder, mutate)
                with self.assertRaisesRegex(ValueError, "unsafe, duplicate|membership is incomplete"):
                    publication.verify_selection(folder)

    def test_changed_authored_summary_cannot_reclassify_saved_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = self._fixture(directory)
            path = folder / "summary.json"
            summary = json.loads(path.read_text())
            summary["groups"][0]["comparisons"][1]["classification"] = "bounded-benefit"
            path.write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, "historical summary differs"):
                publication.verify_selection(folder)
