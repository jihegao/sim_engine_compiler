"""P2 regression: replace binding files while actual raw callback is in progress."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import test_publication_target_v1 as fixture
from publication_target_v1 import BindingError
from publication_snapshot_v2 import captured_binding, derive_captured_reader, captured_execution

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("snapshot_reader", HERE / "independent-postpublication-reader-v3.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ArtifactSnapshotTests(unittest.TestCase):
    def run_fixture(self, mutate=None, target=True, product=True, corrupt_target=None, aba=False, code_aba=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            binding = root / "original.json"
            binding.write_bytes((HERE / "publication-binding-v1.json").read_bytes())
            target_path = root / "target.json" if target else None
            product_path = root / "product.json" if product else None
            if target_path:
                target_path.write_bytes(corrupt_target or json.dumps(fixture.target()).encode())
            if product_path:
                product_path.write_bytes(json.dumps(fixture.product_target()).encode())
            captured = {"binding":binding.read_bytes(), "target":target_path.read_bytes() if target_path else None,
                        "product":product_path.read_bytes() if product_path else None}
            observed = fixture.refs(fixture.LATER if target else fixture.PUB)
            if product:
                observed = observed.replace(fixture.BINDING["product_commit"], fixture.PRODUCT_LATER)
            route = fixture.ReaderRouteTests()
            raw_result = route.raw(fixture.LATER if target else fixture.PUB)
            raw_result.stdout = json.dumps({**json.loads(raw_result.stdout), "remote_refs":observed}).encode()
            paths = {"binding":binding, "target":target_path, "product":product_path}
            code_paths = {}
            for name, filename in (("gate", "publication_target_v1.py"), ("protocol", "publication_snapshot_v2.py"), ("reader", "original-published-snapshot-reader-v3.py")):
                path = root / filename
                path.write_bytes((HERE / filename).read_bytes())
                paths[name] = path
                captured[name] = path.read_bytes()
                code_paths[name] = path
            def raw(*args, **kwargs):
                payload = json.loads(kwargs["input"])
                stdin_binding = bytes.fromhex(payload["binding"])
                self.assertEqual(stdin_binding, captured["binding"])
                child_binding = captured_binding(stdin_binding, fixture.BSHA)
                self.assertEqual(child_binding["publication"]["commit"], fixture.PUB)
                self.assertEqual(args[0][-2], "-c")
                for name, key in (("gate", "publication_target_v1"), ("protocol", "publication_snapshot_v2"), ("reader", "reader")):
                    self.assertEqual(bytes.fromhex(payload["sources"][key]), captured[name])
                if code_aba:
                    paths[code_aba].write_bytes(b"raise RuntimeError('mutable-path-code-must-not-execute')\n")
                    key = {"gate":"publication_target_v1", "protocol":"publication_snapshot_v2", "reader":"reader"}[code_aba]
                    self.assertEqual(bytes.fromhex(payload["sources"][key]), captured[code_aba])
                    paths[code_aba].write_bytes(captured[code_aba])
                if aba:
                    replacement = json.loads(captured["binding"])
                    replacement["publication"]["commit"] = fixture.WRONG
                    paths["binding"].write_bytes(json.dumps(replacement).encode())
                    # The child consumes stdin bytes while the path contains the replacement.
                    self.assertEqual(captured_binding(stdin_binding, fixture.BSHA), fixture.BINDING)
                    self.assertNotEqual(json.loads(paths["binding"].read_bytes()), child_binding)
                    paths["binding"].write_bytes(captured["binding"])
                if mutate:
                    name, action = mutate
                    if action == "remove":
                        paths[name].unlink()
                    elif action == "same-semantics":
                        paths[name].write_bytes(captured[name] + b"\n")
                    elif action == "code":
                        paths[name].write_bytes(b"raise RuntimeError('changed')\n")
                    else:
                        value = json.loads(captured[name]); value["commit"] = fixture.WRONG
                        paths[name].write_bytes(json.dumps(value).encode())
                return raw_result
            with patch.object(reader, "HERE", root), patch.object(reader, "BINDING", binding), patch.object(reader, "git", route.fake_git), patch.object(reader, "refs", return_value=observed), patch.object(reader, "describe", fixture.describe), patch.object(reader, "ancestor", fixture.ancestor), patch.object(reader.subprocess, "run", side_effect=raw) as raw_mock:
                result = reader.run("current-target", target_path, product_path)
                raw_mock.assert_called_once()
            return result, captured

    def test_unchanged_explicit_bindings_hash_exact_validated_bytes(self):
        result, captured = self.run_fixture()
        self.assertEqual(result["schema"], "simlox-postpublication-replay/v3")
        self.assertEqual(result["decision"], "GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY")
        self.assertEqual(result["explicit_target_binding_sha256"], hashlib.sha256(captured["target"]).hexdigest())
        self.assertEqual(result["explicit_product_binding_sha256"], hashlib.sha256(captured["product"]).hexdigest())

    def test_default_original_bindings_positive(self):
        result, captured = self.run_fixture(target=False, product=False)
        self.assertEqual(result["decision"], "GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY")
        self.assertIsNone(result["explicit_target_binding_sha256"])
        self.assertIsNone(result["explicit_product_binding_sha256"])

    def changed(self, name, action="different"):
        with self.assertRaises(BindingError) as caught:
            self.run_fixture(mutate=(name, action))
        self.assertEqual(caught.exception.code, "BINDING_ARTIFACT_CHANGED")

    def test_target_replaced_during_raw_rejects_before_go(self):
        self.changed("target")

    def test_product_replaced_during_raw_rejects_before_go(self):
        self.changed("product")

    def test_original_binding_replaced_during_raw_rejects_before_go(self):
        self.changed("binding")

    def test_same_semantics_with_changed_bytes_rejects_all_three_artifacts(self):
        for name in ("binding", "target", "product"):
            with self.subTest(name=name):
                self.changed(name, "same-semantics")

    def test_deleted_artifact_rejects_before_go(self):
        for name in ("binding", "target", "product"):
            with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                self.run_fixture(mutate=(name, "remove"))

    def test_duplicate_key_rejected_from_exact_snapshot(self):
        data = json.dumps(fixture.target()).encode()
        with self.assertRaises(BindingError) as caught:
            self.run_fixture(corrupt_target=data[:-1] + b', "commit":"' + fixture.WRONG.encode() + b'"}')
        self.assertEqual(caught.exception.code, "DUPLICATE_BINDING_KEY")

    def test_binding_replacement_and_restoration_cannot_change_child_snapshot(self):
        result, captured = self.run_fixture(aba=True)
        self.assertEqual(result["decision"], "GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY")
        self.assertEqual(result["subordinate_binding_transport"], "captured-code-and-binding-stdin-bundle")
        self.assertEqual(result["publication_binding_sha256"], hashlib.sha256(captured["binding"]).hexdigest())

    def test_missing_wrong_or_replaced_subordinate_payload_rejects(self):
        for data in (b"", b"{}", json.dumps({**fixture.BINDING, "case_version":"wrong"}).encode()):
            with self.subTest(data=data[:20]), self.assertRaises(BindingError) as caught:
                captured_binding(data, fixture.BSHA)
            self.assertEqual(caught.exception.code, "CAPTURED_PUBLICATION_BINDING_MISMATCH")

    def test_shared_subordinate_parser_rejects_duplicate_keys(self):
        data = b'{"publication":{},"publication":{}}'
        with self.assertRaises(BindingError) as caught:
            captured_binding(data, hashlib.sha256(data).hexdigest())
        self.assertEqual(caught.exception.code, "DUPLICATE_BINDING_KEY")

    def test_subordinate_exact_derivation_uses_stdin_not_binding_path(self):
        original = (HERE / "independent-postpublication-reader-v1.py").read_text(encoding="utf8")
        actual = (HERE / "original-published-snapshot-reader-v3.py").read_text(encoding="utf8")
        self.assertEqual(actual, derive_captured_reader(original, fixture.BSHA))
        self.assertIn("captured_binding(sys.stdin.buffer.read(),", actual)
        self.assertNotIn("publication_binding=json.loads((Path(__file__).parent/", actual)

    def test_module_and_reader_aba_preserve_captured_execution(self):
        for name in ("gate", "protocol", "reader"):
            with self.subTest(name=name):
                result, captured = self.run_fixture(code_aba=name)
                field = {"gate":"gate_sha256", "protocol":"snapshot_protocol_sha256", "reader":"snapshot_reader_sha256"}[name]
                self.assertEqual(result[field], hashlib.sha256(captured[name]).hexdigest())

    def test_permanent_module_and_reader_change_reject_before_go(self):
        for name in ("gate", "protocol", "reader"):
            with self.subTest(name=name):
                self.changed(name, "code")

    def test_capture_requires_trusted_module_pins_before_child(self):
        for field, code in (("GATE_SHA256", "CAPTURED_GATE_CHANGED"), ("PROTOCOL_SHA256", "CAPTURED_PROTOCOL_CHANGED")):
            with self.subTest(field=field), patch.object(reader, field, "0" * 64), self.assertRaises(BindingError) as caught:
                self.run_fixture()
            self.assertEqual(caught.exception.code, code)


class CapturedCodeBootstrapTests(unittest.TestCase):
    def bundle(self, folder):
        sources = {
            "publication_target_v1": (folder / "gate.py", b"VALUE='captured-gate'\n"),
            "publication_snapshot_v2": (folder / "protocol.py", b"VALUE='captured-protocol'\n"),
            "reader": (folder / "reader.py", b"import publication_target_v1 as g, publication_snapshot_v2 as p, sys\nprint(g.VALUE,p.VALUE,sys.stdin.buffer.read().decode())\n")}
        return sources, captured_execution(b"original-binding", sources)

    def execute(self, command, payload):
        return subprocess.run([sys.executable, "-E", "-B", "-c", command], input=payload, capture_output=True)

    def test_actual_bootstrap_uses_captured_code_when_all_paths_are_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            sources, (command, payload) = self.bundle(Path(d))
            for path, data in sources.values():
                path.write_bytes(b"raise RuntimeError('path replacement executed')\n")
            result = self.execute(command, payload)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), b"captured-gate captured-protocol original-binding")

    def test_actual_bootstrap_rejects_tampered_code_even_with_claimed_digest(self):
        with tempfile.TemporaryDirectory() as d:
            sources, (command, payload) = self.bundle(Path(d))
            for name in sources:
                changed = json.loads(payload)
                changed["sources"][name] = b"print('untrusted GO')\n".hex()
                result = self.execute(command, json.dumps(changed).encode())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"CAPTURED_CODE_MISMATCH", result.stderr)
                self.assertNotIn(b"untrusted GO", result.stdout)
            changed["expected"] = {name:hashlib.sha256(b"print('untrusted GO')\n").hexdigest()}
            result = self.execute(command, json.dumps(changed).encode())
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"INVALID_EXECUTION_BUNDLE", result.stderr)

    def test_actual_bootstrap_rejects_missing_code_and_binding(self):
        with tempfile.TemporaryDirectory() as d:
            sources, (command, payload) = self.bundle(Path(d))
            for name in sources:
                changed = json.loads(payload); del changed["sources"][name]
                result = self.execute(command, json.dumps(changed).encode())
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"MISSING_CAPTURED_CODE", result.stderr)
            changed = json.loads(payload); changed["binding"] = b"replacement".hex()
            result = self.execute(command, json.dumps(changed).encode())
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"CAPTURED_PUBLICATION_BINDING_MISMATCH", result.stderr)

    def test_actual_bootstrap_rejects_duplicate_execution_keys(self):
        with tempfile.TemporaryDirectory() as d:
            sources, (command, payload) = self.bundle(Path(d))
            duplicate = payload[:-1] + b',"binding":"00"}'
            result = self.execute(command, duplicate)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"DUPLICATE_EXECUTION_KEY", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
