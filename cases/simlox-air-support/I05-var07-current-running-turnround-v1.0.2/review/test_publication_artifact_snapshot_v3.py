"""P2 regression: replace binding files while actual raw callback is in progress."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_publication_target_v1 as fixture
from publication_target_v1 import BindingError
from publication_snapshot_v2 import captured_binding, derive_captured_reader, captured_execution

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("snapshot_reader", HERE / "independent-postpublication-reader-v4.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ArtifactSnapshotTests(unittest.TestCase):
    def run_fixture(self, mutate=None, target=True, product=True, corrupt_target=None, aba=False, code_aba=None, source_aba=False, corrupt_source=False, future_source=None, future_action="changed", mode="current-target", observed_commit=None):
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
            observed_commit = observed_commit or (fixture.LATER if target else fixture.PUB)
            observed = fixture.refs(observed_commit)
            if product:
                observed = observed.replace(fixture.BINDING["product_commit"], fixture.PRODUCT_LATER)
            route = fixture.ReaderRouteTests()
            raw_result = route.raw(observed_commit)
            raw_result.stdout = json.dumps({**json.loads(raw_result.stdout), "remote_refs":observed}).encode()
            paths = {"binding":binding, "target":target_path, "product":product_path}
            for name in ("input", "manifest", "inherited_reader"):
                relative = fixture.BINDING[name]["path"]
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((reader.ROOT / relative).read_bytes())
                if name == "inherited_reader":
                    paths["source_reader"] = path
                    captured["source_reader"] = path.read_bytes()
            if corrupt_source:
                paths["source_reader"].write_bytes(b"raise RuntimeError('unverified source')\n")
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
            original_read_text = Path.read_text
            def no_source_reopen(path, *args, **kwargs):
                if path == paths["source_reader"]:
                    raise AssertionError("verified source path must not be reopened for derivation")
                return original_read_text(path, *args, **kwargs)
            def derive(original, binding_sha):
                if source_aba:
                    paths["source_reader"].write_bytes(b"raise RuntimeError('ABA unverified source')\n")
                self.assertEqual(original, captured["source_reader"].decode('utf8').replace('\r\n','\n'))
                result = derive_captured_reader(original, binding_sha)
                if source_aba:
                    paths["source_reader"].write_bytes(captured["source_reader"])
                return result
            def routed_git(*args, **kwargs):
                if future_source and args[0] == "show" and args[1] == fixture.LATER + ":" + fixture.BINDING[future_source]["path"]:
                    if future_action == "missing":
                        raise BindingError("GIT_OBSERVATION_FAILED", "selected target source missing")
                    return SimpleNamespace(stdout=b"different version source")
                return route.fake_git(*args, **kwargs)
            with patch.object(Path, "read_text", no_source_reopen), patch.object(reader, "derive_captured_reader", side_effect=derive), patch.object(reader, "ROOT", root), patch.object(reader, "HERE", root), patch.object(reader, "BINDING", binding), patch.object(reader, "git", routed_git), patch.object(reader, "refs", return_value=observed), patch.object(reader, "describe", fixture.describe), patch.object(reader, "ancestor", fixture.ancestor), patch.object(reader.subprocess, "run", side_effect=raw) as raw_mock:
                try:
                    result = reader.run(mode, target_path, product_path)
                except BindingError:
                    if corrupt_source or (future_source and mode == "current-target"):
                        raw_mock.assert_not_called()
                    raise
                raw_mock.assert_called_once()
            return result, captured

    def test_unchanged_explicit_bindings_hash_exact_validated_bytes(self):
        result, captured = self.run_fixture()
        self.assertEqual(result["schema"], "simlox-postpublication-replay/v4")
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

    def test_verified_original_source_aba_uses_same_captured_buffer(self):
        result, captured = self.run_fixture(source_aba=True)
        self.assertEqual(result["decision"], "GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY")

    def test_original_source_permanent_change_rejects_before_go(self):
        self.changed("source_reader", "code")

    def test_unverified_original_source_rejects_before_child(self):
        with self.assertRaises(BindingError) as caught:
            self.run_fixture(corrupt_source=True)
        self.assertEqual(caught.exception.code, "LOCAL_SOURCE_MISMATCH")

    def test_current_target_altered_source_anchors_reject_before_child(self):
        for name in ("input", "manifest", "inherited_reader"):
            with self.subTest(name=name), self.assertRaises(BindingError) as caught:
                self.run_fixture(future_source=name)
            self.assertEqual(caught.exception.code, "CURRENT_TARGET_SOURCE_MISMATCH")

    def test_current_target_missing_source_anchors_reject_before_child(self):
        for name in ("input", "manifest", "inherited_reader"):
            with self.subTest(name=name), self.assertRaises(BindingError) as caught:
                self.run_fixture(future_source=name, future_action="missing")
            self.assertEqual(caught.exception.code, "GIT_OBSERVATION_FAILED")

    def test_historical_source_identity_survives_future_source_evolution(self):
        for name in ("input", "manifest", "inherited_reader"):
            for action in ("changed", "missing"):
                with self.subTest(name=name, action=action):
                    result, captured = self.run_fixture(target=False, mode="historical-publication", observed_commit=fixture.LATER, future_source=name, future_action=action)
                    self.assertEqual(result["decision"], "GO_BOUNDED_HISTORICAL_PUBLICATION_READONLY_REPLAY")
                    self.assertIsNone(result["source_provenance"]["current_target_commit"])
                    self.assertEqual(result["source_provenance"]["original_commit"], fixture.PUB)


class CapturedCodeBootstrapTests(unittest.TestCase):
    def bundle(self, folder):
        sources = {
            "publication_target_v1": (folder / "gate.py", b"VALUE='captured-gate'\n"),
            "publication_snapshot_v2": (folder / "protocol.py", b"VALUE='captured-protocol'\n"),
            "reader": (folder / "reader.py", b"import publication_target_v1 as g, publication_snapshot_v2 as p, sys\nprint(g.VALUE,p.VALUE,sys.stdin.buffer.read().decode())\n")}
        return sources, captured_execution(b"original-binding", sources)

    def execute(self, command, payload, cwd=None, env=None):
        return subprocess.run([sys.executable, "-I", "-E", "-B", "-c", command], input=payload, capture_output=True, cwd=cwd, env=env)

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

    def test_isolated_bootstrap_rejects_checkout_and_environment_shadow_imports(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            sources, (command, payload) = self.bundle(folder)
            for name in ('json.py', 'hashlib.py'):
                (folder / name).write_text("raise RuntimeError('checkout shadow module imported')\n")
            env = dict(os.environ, PYTHONPATH=d, PYTHONHOME=str(folder / 'invalid-home'))
            result = self.execute(command, payload, cwd=folder, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), b"captured-gate captured-protocol original-binding")


if __name__ == "__main__":
    unittest.main(verbosity=2)
