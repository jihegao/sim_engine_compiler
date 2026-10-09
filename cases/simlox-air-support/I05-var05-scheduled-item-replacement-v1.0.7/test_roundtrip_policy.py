import copy, json, pathlib, tempfile, unittest
from decimal import Decimal
from check_roundtrip import compare_documents, double_equal, parse_native

ROOT=pathlib.Path(__file__).resolve().parent
V104=ROOT/"preserved-history"/"v104-roundtrip-failure"/"run"
SOURCE=parse_native(ROOT/"native-input.json")
EXPORT=parse_native(V104/"roundtrip-raw.json")

def tables(doc): return {table["name"]:table for table in doc["model"]["tables"]}

class RoundtripPolicyTests(unittest.TestCase):
    def test_observed_v104_representation_matches_prospective_policy(self):
        issues,counts=compare_documents(SOURCE,EXPORT)
        self.assertEqual([],issues)
        self.assertEqual(25,counts["authored_populated_tables"])
        self.assertEqual(11,counts["empty_tables"])
        self.assertEqual(24,counts["double_representation_changes"])
        self.assertEqual(11,counts["null_placeholders"])

    def test_json_decimal_tokens_are_not_rounded_to_binary_float(self):
        with tempfile.TemporaryDirectory() as d:
            file=pathlib.Path(d)/"x.json";file.write_text('{"x":1.50000000000000001}',encoding="utf-8")
            value=parse_native(file)["x"]
        self.assertEqual(Decimal("1.50000000000000001"),value)
        self.assertFalse(double_equal(Decimal("1.5"),value))

    def test_huge_integer_in_double_column_returns_mismatch_without_exception(self):
        self.assertFalse(double_equal(Decimal("5.0"),10**10000))

    def test_exact_binary64_serializer_spelling_is_the_only_numeric_normalization(self):
        self.assertTrue(double_equal(Decimal("0.3333333333333333"),Decimal("0.33333333333333331")))
        self.assertFalse(double_equal(Decimal("1.5"),Decimal("1.50000000000000001")))

    def test_boolean_cannot_masquerade_as_double(self):
        altered=copy.deepcopy(EXPORT);row=tables(altered)["ChangesItemReplacement"]["instances"][0]["rows"][0];row[4]=True
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("ChangesItemReplacement" in issue for issue in issues))

    def test_empty_table_placeholder_must_be_all_null(self):
        altered=copy.deepcopy(EXPORT);row=tables(altered)["TaskResource"]["instances"][0]["rows"][0];row[0]="unexpected"
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("TaskResource" in issue for issue in issues))

    def test_empty_instance_inside_populated_table_must_stay_empty(self):
        source=copy.deepcopy(SOURCE);exported=copy.deepcopy(EXPORT)
        cols=tables(source)["Item"]["columns"]
        tables(source)["Item"]["instances"].append({"instance_name":"SECOND","rows":[]})
        tables(exported)["Item"]["instances"].append({"instance_name":"SECOND","rows":[[None]*len(cols)]})
        issues,_=compare_documents(source,exported);self.assertTrue(any("empty instance inside populated table" in issue for issue in issues))

    def test_malformed_row_width_is_rejected(self):
        altered=copy.deepcopy(EXPORT);tables(altered)["Item"]["instances"][0]["rows"][0].pop()
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("row width changed in Item" in issue for issue in issues))

    def test_extra_populated_row_is_rejected(self):
        altered=copy.deepcopy(EXPORT);item=tables(altered)["Item"]["instances"][0]["rows"];item.append(copy.deepcopy(item[0]))
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("row count changed in Item" in issue for issue in issues))

    def test_optional_null_cell_remains_exact(self):
        altered=copy.deepcopy(EXPORT);tables(altered)["ChangesItemReplacement"]["instances"][0]["rows"][0][5]=Decimal("0")
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("ChangesItemReplacement" in issue for issue in issues))

    def test_nonintegral_double_change_is_rejected(self):
        altered=copy.deepcopy(EXPORT);tables(altered)["ItemReplacement"]["instances"][0]["rows"][0][3]=Decimal("1.0000000001")
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("ItemReplacement" in issue for issue in issues))

    def test_change_row_sub_ulp_change_is_rejected(self):
        altered=copy.deepcopy(EXPORT);tables(altered)["ChangesItemReplacement"]["instances"][0]["rows"][0][4]=Decimal("1.50000000000000001")
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("ChangesItemReplacement" in issue for issue in issues))

    def test_other_cell_types_remain_strict(self):
        altered=copy.deepcopy(EXPORT);tables(altered)["ProblemDescription"]["instances"][0]["rows"][0][0]+=" altered"
        issues,_=compare_documents(SOURCE,altered);self.assertTrue(any("ProblemDescription" in issue for issue in issues))

    def test_table_order_remains_strict(self):
        altered=copy.deepcopy(EXPORT);altered["model"]["tables"][0],altered["model"]["tables"][1]=altered["model"]["tables"][1],altered["model"]["tables"][0]
        issues,_=compare_documents(SOURCE,altered);self.assertIn("table names/order differ",issues)

if __name__=="__main__":unittest.main()
