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

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("snapshot_reader", HERE / "independent-postpublication-reader-v3.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ArtifactSnapshotTests(unittest.TestCase):
    def run_fixture(self, mutate=None, target=True, product=True, corrupt_target=None):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
