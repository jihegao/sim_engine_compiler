"""Executable release-boundary checks for the installable aircraft v0.1 product."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from sim_engine_compiler import (
    ProductError,
    batch_bundle,
    compile_bundle,
    diff_runs,
    inspect_model,
    load_bundle,
    run_bundle,
    seal_business,
    validate_business,
)
from sim_engine_compiler.domains.aircraft_support.pack import PACK
from sim_engine_compiler.identity.common import content_digest
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "src/sim_engine_compiler/examples/aircraft_b1_business.json"


class ProductV01Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.business = json.loads(EXAMPLE.read_text())
        self.bundle_path = self.root / "baseline.simpack"
        compile_bundle(self.business, self.bundle_path)

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "sim_engine_compiler.cli", *map(str, args)],
            text=True,
            capture_output=True,
            cwd=self.root,
            check=False,
        )

    def repack(self, mutate):
        with ZipFile(self.bundle_path) as archive:
            layers = {name: archive.read(name) for name in archive.namelist()}
        manifest = json.loads(layers["manifest.json"])
        mutate(layers, manifest)
        manifest["files"] = {
            name: hashlib.sha256(layers[name]).hexdigest()
            for name in ("business.json", "core.json", "plan.json", "lineage.json")
        }
        manifest["bundle_id"] = content_digest(
            {k: v for k, v in manifest.items() if k != "bundle_id"}
        )
        layers["manifest.json"] = json.dumps(manifest, sort_keys=True).encode()
        output = self.root / "mutated.simpack"
        with ZipFile(output, "w") as archive:
            for name, data in layers.items():
                archive.writestr(name, data)
        return output

    def test_portable_bundle_cli_sdk_and_reference_agree(self):
        bundle = load_bundle(self.bundle_path)
        self.assertEqual(bundle.identity_report["association_status"], "verified")
        self.assertEqual(inspect_model(self.bundle_path)["status"], "valid")
        self.assertEqual(validate_business(self.business)["status"], "valid")
        other_output = self.root / "same-model.simpack"
        compile_bundle(self.business, other_output)
        self.assertEqual(self.bundle_path.read_bytes(), other_output.read_bytes())
        moved = self.root / "different-directory" / "model.simpack"
        moved.parent.mkdir()
        moved.write_bytes(self.bundle_path.read_bytes())
        sdk = run_bundle(moved, seed=7, run_id="paired", observation="full")
        command = self.cli("run", moved, "--seed", "7", "--run-id", "paired")
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout), sdk)
        reference = SimpyReferenceRuntime(
            ExecutionPlan.from_dict(bundle.plan), seed=7
        ).run()
        self.assertEqual(sdk["result"], reference)
        self.assertEqual(sdk["request_identity"]["bundle_binding"]["status"], "matched")

    def test_edit_business_seal_compile_batch_and_diff(self):
        baseline = run_bundle(self.bundle_path, seed=0, run_id="before")
        draft = copy.deepcopy(self.business)
        draft["payload"]["sections"]["support_activities"]["collections"]["activities"][
            0
        ]["definition"]["jobs"][0]["durationMinutes"] = 30
        self.assertEqual(validate_business(draft)["status"], "invalid")
        edited = seal_business(draft["payload"])
        self.assertNotEqual(edited["fingerprint"], self.business["fingerprint"])
        self.assertEqual(validate_business(edited)["status"], "valid")
        edited_path = self.root / "edited.simpack"
        compile_bundle(edited, edited_path)
        edited_run = run_bundle(edited_path, seed=0, run_id="after")
        difference = diff_runs(baseline, edited_run)
        self.assertEqual(difference["status"], "different")
        self.assertIsNotNone(difference["first_trace_difference"])
        self.assertIn("cancelled_sorties", difference["metric_changes"])
        before_path, after_path = self.root / "before.json", self.root / "after.json"
        before_path.write_text(json.dumps(baseline))
        after_path.write_text(json.dumps(edited_run))
        command = self.cli("diff", before_path, after_path)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout), difference)
        self.assertNotEqual(
            baseline["result"]["plan_fingerprint"],
            edited_run["result"]["plan_fingerprint"],
        )
        batch = batch_bundle(
            edited_path, [0, 0, 7], run_id="experiment", worker_threads=2
        )
        self.assertEqual(
            [entry["seed"] for entry in batch["result"]["samples"]], [0, 0, 7]
        )
        self.assertEqual(
            [entry["sample_index"] for entry in batch["result"]["samples"]], [0, 1, 2]
        )
        self.assertEqual(
            batch["result"]["samples"][0]["result"],
            batch["result"]["samples"][1]["result"],
        )
        self.assertNotEqual(
            batch["sample_identities"][0]["identity"]["sample_id"],
            batch["sample_identities"][1]["identity"]["sample_id"],
        )

    def test_old_bundle_index_and_cross_revision_fail_closed(self):
        old = self.repack(
            lambda layers, manifest: manifest.update(compiler_version="0.0.1")
        )
        with self.assertRaises(ProductError) as caught:
            load_bundle(old)
        self.assertEqual(caught.exception.code, "unsupported_producer_version")

        def add_index(layers, manifest):
            plan = json.loads(layers["plan.json"])
            plan["resource_dispatch_index"] = {
                "schema_version": "resource-dispatch-index/v2"
            }
            layers["plan.json"] = json.dumps(plan).encode()

        indexed = self.repack(add_index)
        with self.assertRaises(ProductError) as caught:
            load_bundle(indexed)
        self.assertEqual(caught.exception.code, "unsupported_resource_dispatch_index")

        other = copy.deepcopy(self.business)
        other["payload"]["sections"]["support_activities"]["collections"]["activities"][
            0
        ]["definition"]["jobs"][0]["durationMinutes"] = 30
        other = seal_business(other["payload"])

        def replace_business(layers, manifest):
            layers["business.json"] = json.dumps(other).encode()
            manifest["identity"]["business_fingerprint"] = other["fingerprint"]

        mismatched = self.repack(replace_business)
        with self.assertRaises(ProductError) as caught:
            load_bundle(mismatched)
        self.assertEqual(caught.exception.code, "bundle_association_invalid")

        def unknown_operation(layers, manifest):
            core = json.loads(layers["core.json"])
            core["payload"]["operations"][0]["operation"] = "unregistered.rule/v1"
            core["fingerprint"] = content_digest(
                {"version": core["version"], "payload": core["payload"]}
            )
            layers["core.json"] = json.dumps(core).encode()
            manifest["identity"]["core_fingerprint"] = core["fingerprint"]

        unsupported = self.repack(unknown_operation)
        with self.assertRaises(ProductError) as caught:
            load_bundle(unsupported)
        self.assertEqual(caught.exception.code, "bundle_association_invalid")

    def test_invalid_edit_and_cli_diagnostics(self):
        draft = copy.deepcopy(self.business["payload"])
        draft["sections"]["support_activities"]["collections"]["activities"][0][
            "definition"
        ]["jobs"][0]["durationMinutes"] = -1
        with self.assertRaises(ProductError):
            seal_business(draft)
        draft = copy.deepcopy(self.business["payload"])
        draft["semantic_profile"] = "future-profile-v9"
        with self.assertRaises(ProductError) as caught:
            seal_business(draft)
        self.assertEqual(caught.exception.code, "unsupported_profile")
        with self.assertRaises(ProductError) as caught:
            run_bundle(self.bundle_path, run_id="")
        self.assertEqual(caught.exception.code, "invalid_run_id")
        with self.assertRaises(ProductError) as caught:
            run_bundle(self.bundle_path, until=61)
        self.assertEqual(caught.exception.code, "invalid_horizon")
        bad = self.root / "bad.json"
        bad.write_text('{"version":1,"version":2}')
        command = self.cli("validate", bad)
        self.assertEqual(command.returncode, 2)
        diagnostic = json.loads(command.stdout)["diagnostics"][0]
        self.assertEqual(diagnostic["code"], "invalid_json")
        self.assertEqual(diagnostic["stage"], "load")

    def test_domain_pack_declares_restricted_capability(self):
        capabilities = PACK.capabilities()
        self.assertEqual(
            capabilities["operation_class"], "restricted-aircraft-compatibility"
        )
        self.assertIn("legacy-minute-v1", capabilities["semantic_profiles"])
        self.assertGreater(len(capabilities["operations"]), 0)


if __name__ == "__main__":
    unittest.main()
