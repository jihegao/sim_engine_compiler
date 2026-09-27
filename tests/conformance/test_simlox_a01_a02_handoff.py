"""Portable handoff integrity and semantic mutation checks; no SIMLOX needed."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "cases/simlox-air-support/handoff-v1/portable.py"
spec = importlib.util.spec_from_file_location("a01_a02_portable", TOOL)
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.good = self.root / "good.zip"
        self.result = portable.pack(REPO, self.good)

    @staticmethod
    def formal_verify(path: Path) -> dict:
        with zipfile.ZipFile(path) as archive:
            external_pin = portable.digest(archive.read("manifest.json"))
        return portable.verify_package(path, external_pin)

    def mutant(self, name: str, change, *, update_payload_hash: bool = True) -> Path:
        with zipfile.ZipFile(self.good) as source:
            files = {item: source.read(item) for item in source.namelist()}
        if name == "manifest.json":
            value = json.loads(files[name])
            change(value)
            files[name] = portable.encoded(value)
        elif name == "__remove__":
            files.pop(change)
        else:
            value = json.loads(files[name]) if name.endswith(".json") else files[name]
            changed = change(value)
            files[name] = portable.encoded(value) if changed is None and name.endswith(".json") else changed
            if update_payload_hash:
                manifest = json.loads(files["manifest.json"])
                manifest["payload_files"][name]["sha256"] = portable.digest(files[name])
                manifest["payload_files"][name]["bytes"] = len(files[name])
                if name == "expected-observations.json":
                    manifest["source_fingerprints"]["expected_observations_sha256"] = portable.digest(files[name])
                files["manifest.json"] = portable.encoded(manifest)
        target = self.root / "mutant.zip"
        with zipfile.ZipFile(target, "w") as archive:
            for member, raw in files.items():
                archive.writestr(member, raw)
        return target

    def schema_mutant(self, *, remove: str | None = None, add: str | None = None) -> Path:
        with zipfile.ZipFile(self.good) as source:
            files = {item: source.read(item) for item in source.namelist()}
        manifest = json.loads(files["manifest.json"])
        if remove:
            files.pop(remove)
            manifest["payload_files"].pop(remove)
        if add:
            files[add] = b"self-consistent extra"
            manifest["payload_files"][add] = {"repo_relative_path": add,
                                                "sha256": portable.digest(files[add]),
                                                "bytes": len(files[add])}
        files["manifest.json"] = portable.encoded(manifest)
        target = self.root / "schema-mutant.zip"
        with zipfile.ZipFile(target, "w") as archive:
            for member, raw in files.items():
                archive.writestr(member, raw)
        return target

    def test_deterministic_archive_and_explicit_unverified_status(self):
        second = self.root / "second.zip"
        repeated = portable.pack(REPO, second)
        self.assertEqual(self.good.read_bytes(), second.read_bytes())
        self.assertEqual(self.result, repeated)
        self.assertEqual(self.result["intervals_per_case"], 72)
        self.assertEqual(self.result["engine_status"], "not_run_unverified")
        self.assertEqual(self.result["gui_status"], "pending_private_user_handoff")

    def test_archived_validator_runs_without_source_checkout_or_simlox(self):
        with zipfile.ZipFile(self.good) as archive:
            extracted_tool = self.root / "portable.py"
            extracted_tool.write_bytes(archive.read("portable.py"))
        completed = subprocess.run([sys.executable, str(extracted_tool), "verify", "--zip", str(self.good),
                                    "--manifest-sha256", self.result["manifest_sha256"]],
                                   cwd=self.root, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(completed.stdout)["engine_status"], "not_run_unverified")

    def test_missing_and_tampered_payload_rejected(self):
        with self.assertRaisesRegex(ValueError, "missing/extra package file"):
            self.formal_verify(self.mutant("__remove__", "cases/A01/contract.json"))
        with self.assertRaisesRegex(ValueError, "payload hash/size mismatch"):
            self.formal_verify(self.mutant("README.md", lambda raw: raw + b"changed", update_payload_hash=False))

    def test_wrong_source_and_input_hash_rejected_after_rehash(self):
        with self.assertRaisesRegex(ValueError, "wrong task/schema/source commit"):
            self.formal_verify(self.mutant("manifest.json", lambda doc: doc.update(accepted_source_commit="wrong")))
        def change_input(doc):
            doc["model"]["name"] = "tampered"
        with self.assertRaisesRegex(ValueError, "wrong input/contract source hash"):
            self.formal_verify(self.mutant("cases/A01/native-input.json", change_input))

    def test_wrong_units_identity_and_reservation_profile_rejected(self):
        with self.assertRaisesRegex(ValueError, "wrong units"):
            self.formal_verify(self.mutant("manifest.json", lambda doc: doc["units"].update(hours_to_minutes=1)))
        with self.assertRaisesRegex(ValueError, "event/state profile mismatch"):
            self.formal_verify(self.mutant("expected-observations.json", lambda doc:
                doc["cases"]["A01"]["events"][1].update(aircraft_instance="<TEACH-AIR-010,0>")))
        with self.assertRaisesRegex(ValueError, "event/state profile mismatch"):
            self.formal_verify(self.mutant("expected-observations.json", lambda doc:
                doc["cases"]["A01"]["intervals"][14].update(NSYMR=0)))

    def test_wrong_cutoff_and_false_engine_acceptance_rejected(self):
        with self.assertRaisesRegex(ValueError, "wrong SIMPE cutoff classification"):
            self.formal_verify(self.mutant("expected-observations.json", lambda doc:
                doc["simpe_input_validity"].update(classification="proven_cancel_rule")))
        with self.assertRaisesRegex(ValueError, "engine result falsely accepted"):
            self.formal_verify(self.mutant("consumer-report-template.json", lambda doc:
                doc.update(engine_status="passed", equivalence_status="accepted")))

    def test_manifest_pin_and_windows_path_independence(self):
        with self.assertRaisesRegex(ValueError, "external manifest SHA required"):
            portable.verify_package(self.good)
        with self.assertRaisesRegex(ValueError, "manifest SHA mismatch"):
            portable.verify_package(self.good, "0" * 64)
        changed = self.mutant("manifest.json", lambda doc:
            doc["native_runs"]["A01"][0].update(original_directory_windows="unavailable on AMD128"))
        self.assertEqual(self.formal_verify(changed)["status"],
                         "portable_integrity_and_contract_verified_not_engine_equivalence")

    def test_fixed_membership_and_source_mapping_reject_self_consistent_rehash(self):
        with self.assertRaisesRegex(ValueError, "wrong fixed payload schema"):
            self.formal_verify(self.schema_mutant(remove="gui-checklist.json"))
        with self.assertRaisesRegex(ValueError, "wrong fixed payload schema"):
            self.formal_verify(self.schema_mutant(remove="cases/A01/evidence-index.json"))
        with self.assertRaisesRegex(ValueError, "wrong fixed payload source path"):
            self.formal_verify(self.mutant("manifest.json", lambda doc:
                doc["payload_files"]["cases/A01/evidence-index.json"].update(repo_relative_path="wrong/path")))
        with self.assertRaisesRegex(ValueError, "wrong fixed payload schema"):
            self.formal_verify(self.schema_mutant(add="extra.txt"))

    def test_native_run_and_tool_lineage_cannot_be_erased_by_rehash(self):
        with self.assertRaisesRegex(ValueError, "missing bound native replay"):
            self.formal_verify(self.mutant("manifest.json", lambda doc:
                doc["native_runs"].update(A01=[])))
        with self.assertRaisesRegex(ValueError, "sealed tool fingerprints changed"):
            self.formal_verify(self.mutant("manifest.json", lambda doc:
                doc["sealed_tools_sha256"].update({key: "0" * 64 for key in doc["sealed_tools_sha256"]})))
        with self.assertRaisesRegex(ValueError, "accepted record source hash changed"):
            self.formal_verify(self.mutant("cases/A01/manifest.json", lambda doc:
                doc.update(run_bindings=[{}, {}])))


if __name__ == "__main__":
    unittest.main()
