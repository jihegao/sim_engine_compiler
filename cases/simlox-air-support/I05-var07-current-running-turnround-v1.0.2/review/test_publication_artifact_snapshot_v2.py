"""P2 regression: replace binding files while actual raw callback is in progress."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import test_publication_target_v1 as fixture
from publication_target_v1 import BindingError
from publication_snapshot_v2 import captured_binding, derive_captured_reader

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("snapshot_reader", HERE / "independent-postpublication-reader-v3.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ArtifactSnapshotTests(unittest.TestCase):
    def run_fixture(self, mutate=None, target=True, product=True, corrupt_target=None, aba=False):
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
            def raw(*args, **kwargs):
                self.assertEqual(kwargs["input"], captured["binding"])
                child_binding = captured_binding(kwargs["input"], fixture.BSHA)
                self.assertEqual(child_binding["publication"]["commit"], fixture.PUB)
                if aba:
                    replacement = json.loads(captured["binding"])
                    replacement["publication"]["commit"] = fixture.WRONG
                    paths["binding"].write_bytes(json.dumps(replacement).encode())
                    # The child consumes stdin bytes while the path contains the replacement.
                    self.assertEqual(captured_binding(kwargs["input"], fixture.BSHA), fixture.BINDING)
                    self.assertNotEqual(json.loads(paths["binding"].read_bytes()), child_binding)
                    paths["binding"].write_bytes(captured["binding"])
                if mutate:
                    name, action = mutate
                    if action == "remove":
                        paths[name].unlink()
                    elif action == "same-semantics":
                        paths[name].write_bytes(captured[name] + b"\n")
                    else:
                        value = json.loads(captured[name]); value["commit"] = fixture.WRONG
                        paths[name].write_bytes(json.dumps(value).encode())
                return raw_result
            with patch.object(reader, "BINDING", binding), patch.object(reader, "git", route.fake_git), patch.object(reader, "refs", return_value=observed), patch.object(reader, "describe", fixture.describe), patch.object(reader, "ancestor", fixture.ancestor), patch.object(reader.subprocess, "run", side_effect=raw) as raw_mock:
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
        self.assertEqual(result["subordinate_binding_transport"], "captured-stdin-bytes")
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
