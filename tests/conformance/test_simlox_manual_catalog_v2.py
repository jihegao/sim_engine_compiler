"""Exercise catalog failure modes; these are planning checks, not native conformance."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

LIB = Path(__file__).resolve().parents[2] / "cases/simlox-air-support"
spec = importlib.util.spec_from_file_location("check_catalog_v2", LIB / "tools/check_catalog_v2.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ManualCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("catalog.json", "catalog-v2.json", "manual-coverage-v2.json", "manual-sources-v2.json"):
            shutil.copyfile(LIB / name, self.root / name)

    def edit(self, name, mutate):
        path = self.root / name
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def test_current_planning_catalog_has_complete_table_mapping(self):
        result = checker.check(self.root)
        self.assertEqual(result["cases"], 108)
        self.assertEqual(result["methods"], 108)
        self.assertEqual(result["core_cases"], 26)
        self.assertEqual(result["input_tables"], 133)
        self.assertEqual(result["planned_variants"], 579)

    def test_b03_uses_explicit_mission_type_contract(self):
        catalog = json.loads((self.root / "catalog-v2.json").read_text(encoding="utf-8"))
        coverage = json.loads((self.root / "manual-coverage-v2.json").read_text(encoding="utf-8"))
        b03 = next(c for c in catalog["cases"] if c["case_id"] == "B03")
        method = next(m for m in coverage["methods"] if m["method_id"] == "M-B03")
        self.assertEqual(b03["contract_profile"], "explicit-mission-type-v1")
        self.assertEqual(b03["capability_state"], "explicit_mission_type_v1_planned")
        self.assertIn("COLD-FIRST", b03["minimal_configuration"])
        self.assertIn("HOT-SORTIE", b03["minimal_configuration"])
        self.assertIn("MissionType", method["input_tables"])

    def test_b03_cannot_fall_back_to_unconfirmed_history_trigger(self):
        def replace_contract(d):
            b03 = next(c for c in d["cases"] if c["case_id"] == "B03")
            b03["contract_profile"] = "sortie-history-auto-v1"
        self.edit("catalog-v2.json", replace_contract)
        with self.assertRaisesRegex(ValueError, "wrong explicit mission type contract"):
            checker.check(self.root)

    def test_b03_first_batch_cannot_claim_unused_turnround_table(self):
        def add_turnround(d):
            method = next(m for m in d["methods"] if m["method_id"] == "M-B03")
            method["input_tables"].append("MissionTurnround")
            table = next(t for t in d["input_table_inventory"] if t["table"] == "MissionTurnround")
            table["method_ids"].append("M-B03")
            table["method_ids"].sort()
        self.edit("manual-coverage-v2.json", add_turnround)
        with self.assertRaisesRegex(ValueError, "mission type mapping incomplete"):
            checker.check(self.root)

    def test_c03_cannot_be_replaced_by_staggered_equipment_contention(self):
        def replace_contract(d):
            c03 = next(c for c in d["cases"] if c["case_id"] == "C03")
            c03["minimal_configuration"] = "错开两个任务并争用一台设备"
        self.edit("catalog-v2.json", replace_contract)
        with self.assertRaisesRegex(ValueError, "two-aircraft contention contract missing"):
            checker.check(self.root)

    def test_catalog_counts_cannot_be_self_consistent_but_incomplete(self):
        def remove_case(d):
            d["cases"] = [c for c in d["cases"] if c["case_id"] != "K09"]
            d["case_count"] -= 1
            d["extension_case_count"] -= 1
        self.edit("catalog-v2.json", remove_case)
        with self.assertRaisesRegex(ValueError, "wrong case count"):
            checker.check(self.root)

    def test_missing_table_case_link_is_rejected(self):
        self.edit("manual-coverage-v2.json", lambda d: d["input_table_inventory"][0].update(method_ids=[]))
        with self.assertRaisesRegex(ValueError, "missing/stale method mapping"):
            checker.check(self.root)

    def test_inconsistent_prerequisites_are_rejected(self):
        def cycle(d):
            by_id = {c["case_id"]: c for c in d["cases"]}
            by_id["A01"]["instructional_prerequisites"] = ["A02"]
        self.edit("catalog-v2.json", cycle)
        with self.assertRaisesRegex(ValueError, "inconsistent prerequisites"):
            checker.check(self.root)

    def test_consistent_but_cyclic_prerequisites_are_rejected(self):
        def cycle(d):
            by_id = {c["case_id"]: c for c in d["cases"]}
            by_id["A05"]["requires"].append("A06")
            by_id["A05"]["instructional_prerequisites"].append("A06")
            by_id["A06"]["requires"].append("A05")
            by_id["A06"]["instructional_prerequisites"].append("A05")
        self.edit("catalog-v2.json", cycle)
        with self.assertRaisesRegex(ValueError, "prerequisite cycle"):
            checker.check(self.root)

    def test_manual_method_cannot_gain_native_acceptance(self):
        self.edit("manual-coverage-v2.json", lambda d: d["methods"][0].update(native_scope_state="verified"))
        with self.assertRaisesRegex(ValueError, "unsupported native method evidence"):
            checker.check(self.root)

    def test_documentation_cannot_promote_accepted_evidence(self):
        def promote(d):
            next(c for c in d["cases"] if c["case_id"] == "A01")["status"] = "published"
        self.edit("catalog-v2.json", promote)
        with self.assertRaisesRegex(ValueError, "evidence promotion"):
            checker.check(self.root)

    def test_new_case_cannot_gain_a_run_artifact(self):
        def artifact(d):
            next(c for c in d["cases"] if not c["core_case"])["artifact_ref"] = "imagined-native-run"
        self.edit("catalog-v2.json", artifact)
        with self.assertRaisesRegex(ValueError, "unsupported evidence"):
            checker.check(self.root)

    def test_invalid_page_or_uncovered_section_is_rejected(self):
        self.edit("manual-coverage-v2.json", lambda d: d["methods"][0].update(pdf_pages=[[997,998]]))
        with self.assertRaisesRegex(ValueError, "invalid page range"):
            checker.check(self.root)

    def test_legacy_catalog_cannot_be_silently_rewritten(self):
        self.edit("catalog.json", lambda d: d["cases"][0].update(verified_features=["all SIMLOX methods"]))
        with self.assertRaisesRegex(ValueError, "legacy catalog changed"):
            checker.check(self.root)


if __name__ == "__main__":
    unittest.main()
