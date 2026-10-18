"""Isolated corruption controls; synthetic logs/output are never native evidence."""
import copy,json,shutil,tempfile,unittest
from pathlib import Path
from check_exchange_v2 import seal,trusted,check_raw
from precision_contract_v2 import strict_json,validate
ROOT=Path(__file__).parent
class BindingControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'component';self.root.mkdir()
        for rel in ['contract.json','native-input.json','prospective-export-full-typed-model-v1.json','source-snapshots/approved-author-method-v2.json']:
            p=self.root/rel;p.parent.mkdir(exist_ok=True);shutil.copyfile(ROOT/rel,p)
        self.sha=self.bind()
        self.contract,self.expected=trusted(self.root,self.sha)
    def bind(self):
        files=[dict(relative_path=str(p.relative_to(self.root)),**seal(p)) for p in self.root.rglob('*') if p.is_file() and p.name!='component-binding-v2.json']
        path=self.root/'component-binding-v2.json';path.write_text(json.dumps(dict(schema='simlox-k02-dtim-component-binding/v2',files=files)))
        return seal(path)['sha256']
    def alter(self,rel,fn):
        path=self.root/rel;doc=strict_json(path.read_bytes());fn(doc);path.write_text(json.dumps(doc))
    def old_value(self,doc):
        t=next(t for t in doc['model']['tables'] if t['name']=='OperationProfile')
        i=[c['name'] for c in t['columns']].index('DTIM');t['instances'][0]['rows'][0][i]=1/3
    def rejected(self,sha=None):
        with self.assertRaises((ValueError,FileNotFoundError)):trusted(self.root,self.sha if sha is None else sha)
    def raw(self):
        raw=Path(self.temp.name)/'raw';raw.mkdir()
        shutil.copyfile(self.root/'native-input.json',raw/'input.json')
        shutil.copyfile(self.root/'prospective-export-full-typed-model-v1.json',raw/'roundtrip-raw.json')
        physical=Path(self.contract['candidate']['physical_directory']);ip=str(physical/'input.json');op=str(physical/'roundtrip-raw.json')
        for kind,path in [('import',ip),('export',op)]:
            lines=(ROOT/'source-snapshots'/('parent-'+kind+'.log')).read_text().splitlines()
            lines[0]=('Importing data from Json file: ' if kind=='import' else 'Exporting data to Json file: ')+path
            (raw/(kind+'.log')).write_bytes(('\r\n'.join(lines)+'\r\n').encode('ascii'))
        return raw,ip,op
    def test_correct_trusted_positive(self):self.assertEqual(trusted(self.root,self.sha)[1],self.expected)
    def test_actual_target_reporting_positive(self):self.assertEqual(validate(self.expected,self.expected)['target_binary64'],'3fbf9add3746f65e')
    def test_identical_old_pair_rejected(self):
        old=copy.deepcopy(self.expected);self.old_value(old)
        with self.assertRaises(ValueError):validate(old,old)
    def test_altered_oracle(self):self.alter('prospective-export-full-typed-model-v1.json',self.old_value);self.rejected()
    def test_oracle_rebound_manifest_still_method_mismatch(self):
        self.alter('prospective-export-full-typed-model-v1.json',self.old_value);self.rejected(self.bind())
    def test_wrong_external_manifest_sha(self):self.rejected('0'*64)
    def test_missing_external_manifest_sha(self):self.rejected('')
    def test_manifest_corruption(self):
        (self.root/'component-binding-v2.json').write_text('{}');self.rejected()
    def test_altered_contract(self):self.alter('contract.json',lambda d:d.update(version='9.9.9'));self.rejected()
    def test_altered_method_even_rebound_manifest(self):
        self.alter('source-snapshots/approved-author-method-v2.json',lambda d:d['planned_source'].update(sha256='0'*64));self.rejected(self.bind())
    def test_altered_source(self):(self.root/'native-input.json').write_bytes(b'{}');self.rejected()
    def test_missing_oracle(self):(self.root/'prospective-export-full-typed-model-v1.json').unlink();self.rejected()
    def test_byte_count_rejected_even_same_hash(self):
        self.alter('contract.json',lambda d:d['oracle'].update(bytes=d['oracle']['bytes']+1));self.rejected(self.bind())
    def test_synthetic_raw_complete_positive(self):
        raw,ip,op=self.raw();r=check_raw(self.root,raw,self.sha,ip,op);self.assertEqual(r['cells'],381);self.assertFalse(r['publication_GO'])
    def test_copied_input_corruption(self):
        raw,ip,op=self.raw();(raw/'input.json').write_bytes(b'{}')
        with self.assertRaises(ValueError):check_raw(self.root,raw,self.sha,ip,op)
    def test_wrong_physical_provenance(self):
        raw,ip,op=self.raw()
        with self.assertRaises(ValueError):check_raw(self.root,raw,self.sha,ip+'.wrong',op)
    def test_old_raw_rejected_despite_trusted_new_oracle(self):
        raw,ip,op=self.raw();old=copy.deepcopy(self.expected);self.old_value(old);(raw/'roundtrip-raw.json').write_text(json.dumps(old))
        with self.assertRaises(ValueError):check_raw(self.root,raw,self.sha,ip,op)
if __name__=='__main__':unittest.main()
