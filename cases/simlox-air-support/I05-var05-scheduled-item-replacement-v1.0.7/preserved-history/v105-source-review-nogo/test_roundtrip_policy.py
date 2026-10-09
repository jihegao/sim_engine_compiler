import copy, json, pathlib, unittest
from check_roundtrip import compare_documents

ROOT=pathlib.Path(__file__).resolve().parent
V104=ROOT/"preserved-history"/"v104-roundtrip-failure"/"run"
SOURCE=json.loads((ROOT/"native-input.json").read_text(encoding="utf-8"))
EXPORT=json.loads((V104/"roundtrip-raw.json").read_text(encoding="utf-8"))

def tables(doc): return {table["name"]:table for table in doc["model"]["tables"]}

class RoundtripPolicyTests(unittest.TestCase):
    def test_observed_v104_representation_matches_prospective_policy(self):
        issues,counts=compare_documents(SOURCE,EXPORT)
        self.assertEqual([],issues)
        self.assertEqual(25,counts["authored_populated_tables"])
        self.assertEqual(11,counts["empty_tables"])
        self.assertEqual(24,counts["double_representation_changes"])
        self.assertEqual(11,counts["null_placeholders"])

    def test_exact_nonintegral_double_change_is_rejected(self):
        altered=copy.deepcopy(EXPORT); row=tables(altered)["ItemReplacement"]["instances"][0]["rows"][0]; row[3]=1.0000000001
        issues,_=compare_documents(SOURCE,altered); self.assertTrue(any("ItemReplacement" in issue for issue in issues))

    def test_boolean_cannot_masquerade_as_double(self):
        altered=copy.deepcopy(EXPORT); row=tables(altered)["ChangesItemReplacement"]["instances"][0]["rows"][0]; row[4]=True
        issues,_=compare_documents(SOURCE,altered); self.assertTrue(any("ChangesItemReplacement" in issue for issue in issues))

    def test_empty_table_placeholder_must_be_all_null(self):
        altered=copy.deepcopy(EXPORT); row=tables(altered)["TaskResource"]["instances"][0]["rows"][0]; row[0]="unexpected"
        issues,_=compare_documents(SOURCE,altered); self.assertTrue(any("TaskResource" in issue for issue in issues))

    def test_other_cell_types_remain_strict(self):
        altered=copy.deepcopy(EXPORT); row=tables(altered)["ProblemDescription"]["instances"][0]["rows"][0]; row[0]+=" altered"
        issues,_=compare_documents(SOURCE,altered); self.assertTrue(any("ProblemDescription" in issue for issue in issues))

    def test_table_order_remains_strict(self):
        altered=copy.deepcopy(EXPORT); altered["model"]["tables"][0],altered["model"]["tables"][1]=altered["model"]["tables"][1],altered["model"]["tables"][0]
        issues,_=compare_documents(SOURCE,altered); self.assertIn("table names/order differ",issues)

    def test_change_row_semantics_remain_exact(self):
        altered=copy.deepcopy(EXPORT); row=tables(altered)["ChangesItemReplacement"]["instances"][0]["rows"][0]; row[4]=1.5000001
        issues,_=compare_documents(SOURCE,altered); self.assertTrue(any("ChangesItemReplacement" in issue for issue in issues))

if __name__=="__main__": unittest.main()
