import copy,json,math,unittest
from pathlib import Path
from precision_contract import strict_json,validate
O=Path(__file__).parent
class PrecisionControls(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.expected=strict_json((O/'prospective-export-full-typed-model-v1.json').read_bytes())
 def mutated(self):return copy.deepcopy(self.expected)
 def table(self,d,name):return next(t for t in d['model']['tables'] if t['name']==name)
 def dtim(self,d,value):
  t=self.table(d,'OperationProfile');i=[c['name'] for c in t['columns']].index('DTIM');t['instances'][0]['rows'][0][i]=value
 def rejected(self,d):
  with self.assertRaises((ValueError,KeyError,TypeError)):validate(d,self.expected)
 def test_complete_positive(self):self.assertEqual(validate(self.expected,self.expected)['cells'],381)
 def test_member_order_presentation_only(self):
  d=dict(reversed(list(self.expected.items())));self.assertEqual(validate(d,self.expected)['instances'],33)
 def test_old_parent_not_target(self):d=self.mutated();self.dtim(d,1/3);self.rejected(d)
 def test_one_ULP_precision_loss(self):d=self.mutated();self.dtim(d,math.nextafter(0.12345678901234567,math.inf));self.rejected(d)
 def test_string_in_double(self):d=self.mutated();self.dtim(d,'0.12345678901234567');self.rejected(d)
 def test_boolean_not_integer(self):
  d=self.mutated();t=self.table(d,'Control');i=[c['name'] for c in t['columns']].index('NREPS');t['instances'][0]['rows'][0][i]=True;self.rejected(d)
 def test_missing_native_default_instance(self):
  d=self.mutated();t=self.table(d,'Station');t['instances']=[i for i in t['instances'] if i['instance_name']!=''];self.rejected(d)
 def test_null_default_corruption(self):
  d=self.mutated();t=self.table(d,'Station');i=next(i for i in t['instances'] if i['instance_name']=='');i['rows'][0][0]='UNKNOWN';self.rejected(d)
 def test_truncated_row(self):d=self.mutated();self.table(d,'OperationProfile')['instances'][0]['rows'][0].pop();self.rejected(d)
 def test_column_metadata_order(self):d=self.mutated();t=self.table(d,'OperationProfile');t['columns'][0],t['columns'][1]=t['columns'][1],t['columns'][0];self.rejected(d)
 def test_missing_table(self):d=self.mutated();d['model']['tables'].pop();self.rejected(d)
 def test_unexpected_metadata(self):d=self.mutated();d['model']['tables'][0]['hidden_new_behavior']=True;self.rejected(d)
 def test_duplicate_JSON_keys(self):
  with self.assertRaises(ValueError):strict_json('{"model":{},"model":{}}')
 def test_nonfinite_JSON_constant(self):
  for v in ['NaN','Infinity','-Infinity']:
   with self.assertRaises(ValueError):strict_json('{"value":'+v+'}')
if __name__=='__main__':unittest.main()
