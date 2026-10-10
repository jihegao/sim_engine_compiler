"""Pure publication identity regressions; fabricated Git observations are not native evidence."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from publication_target_v1 import BindingError, derive_snapshot_reader, parse_refs, published_index, require_stable_refs, verify

HERE = Path(__file__).resolve().parent
BINDING = json.loads((HERE / "publication-binding-v1.json").read_bytes())
BSHA = hashlib.sha256((HERE / "publication-binding-v1.json").read_bytes()).hexdigest()
PUB = BINDING["publication"]["commit"]
TREE = BINDING["publication"]["tree"]
PARENT = BINDING["publication"]["parents"][0]
LATER = "1" * 40
WRONG = "2" * 40
LATER_TREE = "3" * 40
PRODUCT_LATER = "5" * 40
PRODUCT_TREE = "6" * 40
INDEX_BYTES = subprocess.check_output(["git", "--no-replace-objects", "show", PUB + ":" + BINDING["publication_index"]["path"]], cwd=HERE)


def refs(commit=PUB):
    return BINDING["product_commit"] + "\trefs/heads/main\n" + (commit + "\trefs/heads/simlox/main\n" if commit else "")


def describe(commit):
    if commit == BINDING["product_commit"]:
        return {"tree": "7" * 40, "parents": []}
    if commit == PRODUCT_LATER:
        return {"tree": PRODUCT_TREE, "parents": [BINDING["product_commit"]]}
    if commit == PUB:
        return {"tree": TREE, "parents": BINDING["publication"]["parents"]}
    if commit == LATER:
        return {"tree": LATER_TREE, "parents": [PUB, WRONG]}
    raise BindingError("UNAVAILABLE_COMMIT", commit)


def ancestor(older, newer):
    return (older == PUB and newer in (PUB, LATER)) or (older == BINDING["product_commit"] and newer == PRODUCT_LATER)


def target():
    return {"schema": "simlox-expected-publication-target/v1", "publication_binding_sha256": BSHA,
            **{k: BINDING[k] for k in ("repository", "remote", "ref", "package", "case_version", "run_id")},
            "commit": LATER, "tree": LATER_TREE, "provenance": "explicit independently reviewed future publication fixture; pure validator test only"}


def product_target():
    return {"schema": "simlox-expected-product-reference/v1", "publication_binding_sha256": BSHA,
            "repository": BINDING["repository"], "remote": "origin", "ref": "refs/heads/main",
            "commit": PRODUCT_LATER, "tree": PRODUCT_TREE, "provenance": "pure official-provenance fixture",
            "independent_receipt": "pure independent-receipt fixture"}


class GateTests(unittest.TestCase):
    def gate(self, text, mode="current-target", requested=None, binding=None, lookup=describe, product=None):
        return verify(binding or BINDING, text, lookup, ancestor, mode, requested, BSHA, product)

    def rejected(self, code, text, **kwargs):
        with self.assertRaises(BindingError) as caught:
            self.gate(text, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_correct_commit_and_tree_positive(self):
        self.assertEqual(self.gate(refs())["decision"], "CURRENT_TARGET_IDENTITY_VERIFIED")

    def test_missing_target_even_when_product_main_correct(self):
        self.rejected("MISSING_TARGET_REF", refs(None))

    def test_parent_only_target(self):
        self.rejected("TARGET_COMMIT_MISMATCH", refs(PARENT))

    def test_wrong_commit(self):
        self.rejected("TARGET_COMMIT_MISMATCH", refs(WRONG))

    def test_wrong_publication_tree(self):
        b = copy.deepcopy(BINDING); b["publication"]["tree"] = "4" * 40
        self.rejected("PUBLICATION_TREE_MISMATCH", refs(), binding=b)

    def test_wrong_expected_later_tree(self):
        t = target(); t["tree"] = TREE
        self.rejected("TARGET_TREE_MISMATCH", refs(LATER), requested=t)

    def test_wrong_merge_parents(self):
        b = copy.deepcopy(BINDING); b["publication"]["parents"].reverse()
        self.rejected("PUBLICATION_PARENT_MISMATCH", refs(), binding=b)

    def test_historical_original_and_later_descendant_positive_distinct_label(self):
        for commit in (PUB, LATER):
            r = self.gate(refs(commit), mode="historical-publication")
            self.assertEqual(r["decision"], "HISTORICAL_PUBLICATION_IDENTITY_VERIFIED")
            self.assertIsNone(r["expected_current_commit"])

    def test_historical_parent_not_publication(self):
        self.rejected("PUBLICATION_NOT_REACHABLE", refs(PARENT), mode="historical-publication")

    def test_historical_unrelated_even_with_similar_tree(self):
        self.rejected("PUBLICATION_NOT_REACHABLE", refs(WRONG), mode="historical-publication")

    def test_later_tip_never_silently_becomes_expected_target(self):
        self.rejected("TARGET_COMMIT_MISMATCH", refs(LATER))

    def test_explicit_later_target_positive(self):
        r = self.gate(refs(LATER), requested=target())
        self.assertEqual((r["expected_current_commit"], r["expected_current_tree"]), (LATER, LATER_TREE))

    def test_explicit_target_version_ref_and_source_provenance(self):
        for key, value in (("case_version", "other"), ("ref", "refs/heads/main"), ("repository", "wrong/repo"), ("publication_binding_sha256", "0" * 64)):
            t = target(); t[key] = value
            self.rejected("TARGET_SOURCE_BINDING" if key == "publication_binding_sha256" else "TARGET_PROVENANCE", refs(LATER), requested=t)

    def test_explicit_target_without_evidence_locator(self):
        t = target(); t["provenance"] = ""
        self.rejected("TARGET_PROVENANCE", refs(LATER), requested=t)

    def test_historical_and_current_target_binding_not_conflated(self):
        self.rejected("AMBIGUOUS_TARGET", refs(LATER), mode="historical-publication", requested=target())

    def test_wrong_product_main(self):
        self.rejected("PRODUCT_REF_MISMATCH", refs().replace(BINDING["product_commit"], WRONG))

    def test_explicit_external_product_positive_both_modes_default_still_rejects(self):
        text = refs().replace(BINDING["product_commit"], PRODUCT_LATER)
        self.rejected("PRODUCT_REF_MISMATCH", text)
        for mode in ("current-target", "historical-publication"):
            r = self.gate(text, mode=mode, product=product_target())
            self.assertEqual((r["expected_product_commit"], r["observed_product_tree"]), (PRODUCT_LATER, PRODUCT_TREE))

    def test_explicit_product_wrong_tree_rejected(self):
        p = product_target(); p["tree"] = TREE
        self.rejected("PRODUCT_TREE_MISMATCH", refs().replace(BINDING["product_commit"], PRODUCT_LATER), product=p)

    def test_explicit_product_source_ref_provenance_rejected(self):
        for field, value in (("schema", "wrong"), ("publication_binding_sha256", "0" * 64), ("repository", "other/repo"), ("ref", BINDING["ref"]), ("provenance", ""), ("independent_receipt", "")):
            p = product_target(); p[field] = value
            self.rejected({"schema":"PRODUCT_SCHEMA", "publication_binding_sha256":"PRODUCT_SOURCE_BINDING"}.get(field,"PRODUCT_PROVENANCE"), refs().replace(BINDING["product_commit"], PRODUCT_LATER), product=p)

    def test_explicit_product_wrong_commit_and_missing_ref(self):
        self.rejected("PRODUCT_REF_MISMATCH", refs(), product=product_target())
        self.rejected("PRODUCT_REF_MISMATCH", PUB + "\trefs/heads/simlox/main\n", product=product_target())

    def test_explicit_product_unrelated_base_rejected(self):
        with patch(__name__ + ".ancestor", return_value=False):
            self.rejected("PRODUCT_BASE_NOT_REACHABLE", refs().replace(BINDING["product_commit"], PRODUCT_LATER), product=product_target())

    def test_external_product_race_rejected(self):
        with self.assertRaises(BindingError) as caught:
            require_stable_refs(refs(), refs().replace(BINDING["product_commit"], PRODUCT_LATER), refs())
        self.assertEqual(caught.exception.code, "REMOTE_REF_CHANGED")

    def test_duplicate_and_malformed_target_ref_rejected(self):
        for text, code in ((refs() + refs(PARENT), "DUPLICATE_REMOTE_REF"), ("garbage\n", "INVALID_REF_RESPONSE")):
            self.rejected(code, text)

    def test_missing_git_object_fails_closed(self):
        def missing(_):
            raise BindingError("GIT_OBSERVATION_FAILED", "object unavailable")
        self.rejected("GIT_OBSERVATION_FAILED", refs(), lookup=missing)

    def test_ref_race_subordinate_or_terminal_rejected(self):
        require_stable_refs(refs(), refs(), refs())
        for observations in ((refs(), refs(PARENT), refs()), (refs(), refs(), refs(LATER))):
            with self.assertRaises(BindingError) as caught:
                require_stable_refs(*observations)
            self.assertEqual(caught.exception.code, "REMOTE_REF_CHANGED")

    def test_later_514_local_index_does_not_change_published_513_snapshot(self):
        live = json.loads(INDEX_BYTES); live["entries"].append({"publication_id":"pure-future-fixture", "case_id":"I05"})
        self.assertEqual(len(live["entries"]), 514)
        reads = []
        def read_blob(commit, path):
            reads.append((commit, path))
            return INDEX_BYTES
        historical = self.gate(refs(LATER), mode="historical-publication")
        snapshot = published_index(BINDING, read_blob)
        self.assertEqual(len(snapshot["entries"]), 513)
        self.assertEqual(reads, [(PUB, BINDING["publication_index"]["path"])])
        self.assertEqual(historical["decision"], "HISTORICAL_PUBLICATION_IDENTITY_VERIFIED")
        self.assertNotEqual(snapshot, live)

    def test_wrong_original_snapshot_append_rejected(self):
        bad = json.loads(INDEX_BYTES); bad["entries"].append({"publication_id":"wrong-snapshot"})
        with self.assertRaises(BindingError) as caught:
            published_index(BINDING, lambda *_: json.dumps(bad).encode())
        self.assertEqual(caught.exception.code, "PUBLISHED_INDEX_MISMATCH")

    def test_derivation_has_only_three_reviewed_replacements(self):
        old = (HERE / "independent-postpublication-reader-v1.py").read_text(encoding="utf8")
        new = (HERE / "original-published-snapshot-reader-v2.py").read_text(encoding="utf8")
        self.assertEqual(new, derive_snapshot_reader(old))
        self.assertEqual(new.count("liveindex=published_index(publication_binding,read_index_blob)"), 1)
        self.assertNotIn("liveindex=parse(W/", new)
        self.assertNotIn(";assert 'a1a44c72f64d754b711abe4095f1111f8a5ba896\\trefs/heads/main' in refs", new)


spec = importlib.util.spec_from_file_location("repaired_reader", HERE / "independent-postpublication-reader-v2.py")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class ReaderRouteTests(unittest.TestCase):
    def fake_git(self, *args, **kwargs):
        if args[:2] == ("remote", "get-url"):
            return SimpleNamespace(stdout=b"git@github.com:jihegao/sim_engine_compiler.git\n")
        if args[0] == "show":
            if args[1].endswith(":" + BINDING["publication_index"]["path"]):
                return SimpleNamespace(stdout=INDEX_BYTES)
            return SimpleNamespace(stdout=(reader.ROOT / args[1].split(":", 1)[1]).read_bytes())
        raise AssertionError(args)

    def raw(self, observed=PUB):
        return SimpleNamespace(returncode=0, stderr=b"", stdout=json.dumps({"decision":"GO_BOUNDED_PUBLISHED_SNAPSHOT_RAW_REPLAY", "run_id":BINDING["run_id"], "source_roles":140, "readonly_pairs":25, "native_calls_by_reviewer":0, "all_commands_terminal":True, "remote_refs":refs(observed)}).encode())

    def test_invalid_target_gate_precedes_raw_subprocess(self):
        for text in (refs(None), refs(PARENT), refs(WRONG)):
            with patch.object(reader, "git", self.fake_git), patch.object(reader, "refs", return_value=text), patch.object(reader, "describe", describe), patch.object(reader, "ancestor", ancestor), patch.object(reader.subprocess, "run") as raw:
                with self.assertRaises(BindingError):
                    reader.run("current-target")
                raw.assert_not_called()

    def test_correct_target_emits_only_new_current_go_after_raw(self):
        with patch.object(reader, "git", self.fake_git), patch.object(reader, "refs", return_value=refs()), patch.object(reader, "describe", describe), patch.object(reader, "ancestor", ancestor), patch.object(reader.subprocess, "run", return_value=self.raw()) as raw:
            result = reader.run("current-target")
            self.assertEqual(result["decision"], "GO_BOUNDED_CURRENT_TARGET_READONLY_REPLAY")
            self.assertNotIn("decision", result["subordinate_raw_evidence"])
            raw.assert_called_once()
            self.assertIn("-E", raw.call_args.args[0])

    def test_actual_tree_mismatch_precedes_raw(self):
        def wrong_tree(commit):
            return {"tree": WRONG, "parents": BINDING["publication"]["parents"]}
        with patch.object(reader, "git", self.fake_git), patch.object(reader, "refs", return_value=refs()), patch.object(reader, "describe", wrong_tree), patch.object(reader.subprocess, "run") as raw:
            with self.assertRaises(BindingError) as caught:
                reader.run("current-target")
            self.assertEqual(caught.exception.code, "PUBLICATION_TREE_MISMATCH")
            raw.assert_not_called()

    def test_post_raw_ref_change_never_emits_go(self):
        with patch.object(reader, "git", self.fake_git), patch.object(reader, "refs", side_effect=[refs(), refs(LATER)]), patch.object(reader, "describe", describe), patch.object(reader, "ancestor", ancestor), patch.object(reader.subprocess, "run", return_value=self.raw()):
            with self.assertRaises(BindingError) as caught:
                reader.run("current-target")
            self.assertEqual(caught.exception.code, "REMOTE_REF_CHANGED")

    def test_actual_local_immutable_commit_object_tree_and_parents(self):
        self.assertEqual(reader.describe(PUB), describe(PUB))

    def test_optimized_assertions_explicitly_rejected_before_network(self):
        p = subprocess.run([sys.executable, "-O", "-X", "utf8", "-B", str(HERE / "independent-postpublication-reader-v2.py")], capture_output=True)
        self.assertEqual(p.returncode, 1)
        r = json.loads(p.stdout)
        self.assertEqual((r["decision"], r["code"]), ("NO_GO_POSTPUBLICATION", "ASSERTS_DISABLED"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
